import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from src.services.chat_transcript import (
    build_general_transcript,
    parse_chat_line,
)

GENERAL_LINE = (
    "[02-09-26 16:07:10.844][info] Got message:ChatMessage{chat=General, "
    "author='JakeMang', text='Rod Stewart - Young Turks'}."
)
SENT_DUPLICATE_LINE = (
    "[02-09-26 16:07:10.847][info] Message ChatMessage{chat=General, "
    "author='JakeMang', text='Rod Stewart - Young Turks'} sent to chat "
    "(id = 0) members."
)
LOCAL_LINE = (
    "[02-09-26 16:07:05.684][info] Got message:ChatMessage{chat=Local, "
    "author='JakeMang', text='hello locals'}."
)
PRIVATE_LINE = (
    "[02-09-26 21:56:54.406][info] Got message:ChatMessage{chat=Private, "
    "author='DoveInProgress', text='true, but i just cant stand bigots'}."
)
FACTION_LINE = (
    "[02-09-26 18:00:00.000][info] Got message:ChatMessage{chat=Faction, "
    "author='SomeGuy', text='faction plans'}."
)
INIT_NOISE_LINE = "[02-09-26 16:05:33.560][info] Start chat server initialization...."
WHISPER_NOISE_LINE = (
    "[02-09-26 21:56:54.304][info] Player 'DoveInProgress' attempt to start "
    "whispering with 'The_Crow'."
)
APOSTROPHE_LINE = (
    "[02-09-26 17:12:33.100][info] Got message:ChatMessage{chat=General, "
    "author='O'Brien', text='it's fine'}."
)
TRAILING_APOSTROPHE_LINE = (
    "[02-09-26 17:13:00.000][info] Got message:ChatMessage{chat=General, "
    "author='JakeMang', text='can't'}."
)


def make_line(hour: int, minute: int, author: str, text: str) -> str:
    return (
        f"[02-09-26 {hour:02d}:{minute:02d}:00.000][info] "
        f"Got message:ChatMessage{{chat=General, author='{author}', text='{text}'}}."
    )


class ParseChatLineTests(unittest.TestCase):
    def test_parses_general_message(self):
        message = parse_chat_line(GENERAL_LINE)

        self.assertIsNotNone(message)
        self.assertEqual(message.author, "JakeMang")
        self.assertEqual(message.text, "Rod Stewart - Young Turks")
        self.assertEqual(message.timestamp, datetime(2026, 9, 2, 16, 7, 10, 844000))

    def test_parses_apostrophes_in_author_and_text(self):
        message = parse_chat_line(APOSTROPHE_LINE)

        self.assertIsNotNone(message)
        self.assertEqual(message.author, "O'Brien")
        self.assertEqual(message.text, "it's fine")

    def test_parses_trailing_apostrophe_in_text(self):
        message = parse_chat_line(TRAILING_APOSTROPHE_LINE)

        self.assertIsNotNone(message)
        self.assertEqual(message.author, "JakeMang")
        self.assertEqual(message.text, "can't")

    def test_rejects_sent_duplicate_line(self):
        self.assertIsNone(parse_chat_line(SENT_DUPLICATE_LINE))

    def test_rejects_non_general_chats(self):
        for line in (LOCAL_LINE, PRIVATE_LINE, FACTION_LINE):
            self.assertIsNone(parse_chat_line(line), line)

    def test_rejects_noise_lines(self):
        for line in (INIT_NOISE_LINE, WHISPER_NOISE_LINE):
            self.assertIsNone(parse_chat_line(line), line)

    def test_rejects_garbage(self):
        self.assertIsNone(parse_chat_line("hello world"))
        self.assertIsNone(parse_chat_line(""))


class BuildTranscriptTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.logs_dir = Path(self._tmp.name) / "Logs"
        self.logs_dir.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def write_chat_log(self, path: Path, lines):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    async def test_formats_and_orders_messages_within_window(self):
        self.write_chat_log(
            self.logs_dir / "2026-09-02_16-05_chat.txt",
            [
                INIT_NOISE_LINE,
                make_line(16, 7, "JakeMang", "good evening"),
                make_line(16, 8, "t0adlicker", "YOUNG HEAAAAARTS"),
                GENERAL_LINE,
            ],
        )
        now = datetime(2026, 9, 2, 21, 0)

        transcript = await build_general_transcript(
            "testuser", 12, logs_dir=self.logs_dir, now=now
        )

        self.assertEqual(
            transcript,
            "[16:07] JakeMang: good evening\n"
            "[16:07] JakeMang: Rod Stewart - Young Turks\n"
            "[16:08] t0adlicker: YOUNG HEAAAAARTS",
        )

    async def test_filters_messages_outside_window(self):
        self.write_chat_log(
            self.logs_dir / "2026-09-02_16-05_chat.txt",
            [
                make_line(8, 0, "EarlyBird", "before the window"),
                make_line(10, 0, "LateBird", "inside the window"),
            ],
        )
        now = datetime(2026, 9, 2, 21, 0)

        transcript = await build_general_transcript(
            "testuser", 12, logs_dir=self.logs_dir, now=now
        )

        self.assertEqual(transcript, "[10:00] LateBird: inside the window")

    async def test_includes_archive_dirs(self):
        self.write_chat_log(
            self.logs_dir / "logs_2026-09-02" / "2026-09-02_04-05_chat.txt",
            [make_line(10, 0, "MorningGuy", "hello from the morning")],
        )
        self.write_chat_log(
            self.logs_dir / "2026-09-02_16-05_chat.txt",
            [make_line(16, 7, "JakeMang", "good evening")],
        )
        now = datetime(2026, 9, 2, 21, 0)

        transcript = await build_general_transcript(
            "testuser", 12, logs_dir=self.logs_dir, now=now
        )

        self.assertEqual(
            transcript,
            "[10:00] MorningGuy: hello from the morning\n"
            "[16:07] JakeMang: good evening",
        )

    async def test_dedupes_messages_across_files(self):
        line = make_line(16, 7, "JakeMang", "good evening")
        self.write_chat_log(
            self.logs_dir / "logs_2026-09-02" / "2026-09-02_04-05_chat.txt",
            [line],
        )
        self.write_chat_log(self.logs_dir / "2026-09-02_16-05_chat.txt", [line])
        now = datetime(2026, 9, 2, 21, 0)

        transcript = await build_general_transcript(
            "testuser", 12, logs_dir=self.logs_dir, now=now
        )

        self.assertEqual(transcript, "[16:07] JakeMang: good evening")

    async def test_returns_empty_when_no_messages_in_window(self):
        self.write_chat_log(
            self.logs_dir / "2026-09-02_16-05_chat.txt",
            [make_line(8, 0, "EarlyBird", "before the window")],
        )
        now = datetime(2026, 9, 2, 21, 0)

        transcript = await build_general_transcript(
            "testuser", 12, logs_dir=self.logs_dir, now=now
        )

        self.assertEqual(transcript, "")

    async def test_truncates_to_most_recent_messages(self):
        lines = [make_line(10, i, f"Player{i}", f"message {i}") for i in range(5)]
        self.write_chat_log(self.logs_dir / "2026-09-02_16-05_chat.txt", lines)
        now = datetime(2026, 9, 2, 21, 0)

        transcript = await build_general_transcript(
            "testuser", 12, logs_dir=self.logs_dir, now=now, max_messages=3
        )

        content_lines = transcript.split("\n")
        self.assertEqual(len(content_lines), 4)
        self.assertEqual(content_lines[-1], "[... 2 older messages omitted ...]")
        self.assertIn("[10:02] Player2: message 2", transcript)
        self.assertIn("[10:04] Player4: message 4", transcript)
        self.assertNotIn("Player0", transcript)
        self.assertNotIn("Player1", transcript)

    async def test_returns_empty_when_logs_dir_missing(self):
        transcript = await build_general_transcript(
            "testuser", 12, logs_dir=self.logs_dir / "does_not_exist"
        )

        self.assertEqual(transcript, "")


if __name__ == "__main__":
    unittest.main()
