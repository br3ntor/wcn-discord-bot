"""
Runs a user-defined callback on new log lines.
"""

import asyncio
import glob
import logging
import os
import subprocess
from typing import Callable, Coroutine


logger = logging.getLogger(__name__)


class RealTimeLogProcessor:
    """
    Monitors a log file for new lines and triggers a callback for each
    new line. Handles log file name changes (e.g. date-prefixed files)
    by polling for newer files and restarting the tail subprocess.

    Args:
        log_directory: Directory containing the log file.
        log_file_pattern: Glob pattern to match the log file (e.g. "*chat.txt").
        line_callback: Async callback invoked for each new line.
    """

    def __init__(
        self,
        log_directory: str,
        log_file_pattern: str,
        line_callback: Callable[[str], Coroutine],
    ):
        self.log_directory = log_directory
        self.log_file_pattern = log_file_pattern
        self.line_callback = line_callback
        self.current_log_file: str | None = None
        self.process = None
        self.watch_task: asyncio.Task | None = None

    def start(self):
        """Start watching the log in a background task."""
        self.watch_task = asyncio.create_task(self.watch())

    async def stop(self):
        """Stop watching and clean up the tail subprocess."""
        if self.watch_task:
            self.watch_task.cancel()
            try:
                await self.watch_task
            except asyncio.CancelledError:
                pass
            self.watch_task = None

    async def watch(self):
        """Poll for new log files and tail the current one."""
        try:
            while True:
                log_files = glob.glob(
                    os.path.join(self.log_directory, self.log_file_pattern)
                )

                if log_files:
                    latest_log_file = max(log_files, key=os.path.getctime)

                    if latest_log_file != self.current_log_file:
                        logger.info(f"New log file detected: {latest_log_file}")

                        if self.process:
                            self.process.terminate()
                            await self.process.wait()
                            self.process = None

                        self.current_log_file = latest_log_file
                        self.process = await asyncio.create_subprocess_exec(
                            "tail",
                            "-Fn 1",
                            latest_log_file,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        logger.info(f"Tailing log file: {latest_log_file}")

                if self.process and self.process.stdout:
                    try:
                        line = await asyncio.wait_for(
                            self.process.stdout.readline(), timeout=5
                        )
                        if line:
                            decoded = line.decode("utf-8").strip()
                            await self.line_callback(decoded)
                        else:
                            # EOF — process closed, retry on next iteration
                            await self.process.wait()
                            self.process = None
                            self.current_log_file = None
                    except asyncio.TimeoutError:
                        pass
                else:
                    logger.warning(
                        "No log file or process, server restarting? Waiting..."
                    )
                    await asyncio.sleep(5)

        except asyncio.CancelledError:
            logger.debug("Watch task cancelled.")
        finally:
            if self.process:
                self.process.terminate()
                await self.process.wait()
                self.process = None
