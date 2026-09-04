"""
Parses Project Zomboid chat logs and builds transcripts for AI summaries.

Only the General (global) chat channel is included; Local, Faction,
Safehouse and Private chats are excluded on purpose.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from src.services.server import get_zomboid_logs_dir

logger = logging.getLogger(__name__)

MAX_MESSAGES = 4000
MAX_TRANSCRIPT_CHARS = 400_000

# Real messages look like:
# [02-09-26 16:07:10.844][info] Got message:ChatMessage{chat=General, author='JakeMang', text='hi'}.
# The "Message ... sent to chat" lines are duplicates and excluded via the
# "Got message:" check.
CHAT_MESSAGE_PATTERN = re.compile(
    r"ChatMessage\{chat=(?P<chat>.*?), author='(?P<author>.*?)', text='(?P<text>.*?)'\}"
)
TIMESTAMP_PATTERN = re.compile(r"^\[(?P<ts>\d{2}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)\]")


@dataclass(frozen=True)
class ChatMessage:
    timestamp: datetime
    author: str
    text: str


def parse_chat_line(line: str) -> ChatMessage | None:
    """Parse a single log line into a general-chat message, or None."""
    if "Got message:" not in line:
        return None

    ts_match = TIMESTAMP_PATTERN.search(line)
    msg_match = CHAT_MESSAGE_PATTERN.search(line)

    if ts_match is None or msg_match is None:
        return None

    if msg_match.group("chat") != "General":
        return None

    try:
        timestamp = datetime.strptime(ts_match.group("ts"), "%d-%m-%y %H:%M:%S.%f")
    except ValueError:
        return None

    return ChatMessage(
        timestamp=timestamp,
        author=msg_match.group("author"),
        text=msg_match.group("text"),
    )


def _candidate_chat_files(logs_dir: Path, window_start: datetime) -> list[Path]:
    """Find chat log files that could fall inside the window.

    Current logs live at the root of the logs dir; older logs get moved
    into logs_YYYY-MM-DD subdirs. Restart intervals mean a file can cover
    times other than its folder's date, so include recent folders plus a
    day of slack and rely on per-line timestamp filtering afterwards.
    """
    files = list(logs_dir.glob("*chat.txt"))

    earliest_date = window_start.date() - timedelta(days=1)
    for archive_dir in logs_dir.glob("logs_*"):
        try:
            dir_date = datetime.strptime(archive_dir.name, "logs_%Y-%m-%d").date()
        except ValueError:
            continue
        if dir_date >= earliest_date:
            files.extend(archive_dir.glob("*chat.txt"))

    return files


def _read_messages(files: list[Path]) -> list[ChatMessage]:
    """Read all candidate files and return general-chat messages."""
    messages: list[ChatMessage] = []
    seen: set[tuple[datetime, str, str]] = set()

    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    message = parse_chat_line(line)
                    if message is None:
                        continue
                    key = (message.timestamp, message.author, message.text)
                    if key in seen:
                        continue
                    seen.add(key)
                    messages.append(message)
        except OSError as e:
            logger.warning("Failed to read chat log %s: %s", path, e)

    return messages


def format_chat_message(message: ChatMessage) -> str:
    return f"[{message.timestamp:%H:%M}] {message.author}: {message.text}"


async def build_general_transcript(
    system_user: str,
    hours: float,
    *,
    logs_dir: Path | None = None,
    now: datetime | None = None,
    max_messages: int = MAX_MESSAGES,
) -> str:
    """Build a transcript of general chat for the last `hours` hours.

    Returns an empty string when there is nothing to summarize. The result
    is capped to the most recent `max_messages` messages / MAX_TRANSCRIPT_CHARS
    characters, with a notice appended when older messages were dropped.
    """
    directory = logs_dir if logs_dir is not None else get_zomboid_logs_dir(system_user)
    current_time = now if now is not None else datetime.now()
    window_start = current_time - timedelta(hours=hours)

    if not directory.is_dir():
        logger.warning("Chat logs directory not found: %s", directory)
        return ""

    files = _candidate_chat_files(directory, window_start)
    if not files:
        return ""

    messages = await asyncio.to_thread(_read_messages, files)
    recent = sorted(
        (m for m in messages if window_start <= m.timestamp <= current_time),
        key=lambda m: m.timestamp,
    )

    if not recent:
        return ""

    selected: list[ChatMessage] = []
    total_chars = 0
    for message in reversed(recent):
        cost = len(format_chat_message(message)) + 1
        if len(selected) >= max_messages or total_chars + cost > MAX_TRANSCRIPT_CHARS:
            break
        selected.append(message)
        total_chars += cost
    selected.reverse()

    lines = [format_chat_message(m) for m in selected]
    if len(selected) < len(recent):
        dropped = len(recent) - len(selected)
        lines.append(f"[... {dropped} older messages omitted ...]")

    return "\n".join(lines)
