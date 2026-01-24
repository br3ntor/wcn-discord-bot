import asyncio
import re

ERROR_TRIGGER_REGEX = re.compile(
    r"PZXmlParserException|FileNotFoundException|AnimNode\.Parse threw an exception",
    re.IGNORECASE,
)

WORKSHOP_ID_REGEX = re.compile(
    r"steamapps/workshop/content/108600/(\d+)", re.IGNORECASE
)


def _scan_file_sync(log_path: str):
    """Synchronous file scan (runs in a thread via asyncio.to_thread)."""
    ids = set()

    with open(log_path, "r", errors="ignore") as f:
        for line in f:
            if not ERROR_TRIGGER_REGEX.search(line):
                continue

            match = WORKSHOP_ID_REGEX.search(line)
            if match:
                ids.add(match.group(1))

    return sorted(ids)


async def extract_workshop_ids(log_path: str):
    """
    Async wrapper that runs the file scan in a thread
    so the asyncio event loop is never blocked.
    """
    return await asyncio.to_thread(_scan_file_sync, log_path)


async def write_ids_to_file(ids, output_path: str):
    """Async wrapper for writing output file."""

    def _write():
        with open(output_path, "w") as f:
            for wid in ids:
                f.write(wid + "\n")

    await asyncio.to_thread(_write)
