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
    This class monitors a log file for new lines and triggers a
    user-defined callback function for each new line. It can handle
    situations where the log file name changes or remains the same after
    a program restart.

    Args:
        log_directory (str): The directory containing the log file.
        log_file_pattern (str): A pattern to match the log file. This can
            be:
                * A filename (e.g., "error.log")
                * A wildcard pattern (e.g., "*.log") to match any file with
                  a specific extension
        line_callback (callable): The function to be called for each new
            line in the log. This function should take a single argument
            (the new line content as a string).

    Attributes:
        log_directory (str): The directory containing the log file
            (read-only).
        log_file_pattern (str): The pattern used to match the log file
            (read-only).
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
        self.current_log_file = None
        self.current_task = None
        self.process = None

    async def tail_log(self, file_path: str):
        """Uses tail to get newly logged line, then run the callback on it.
        Use this if file name doesn't change on restart."""
        try:
            self.process = await asyncio.create_subprocess_exec(
                "tail",
                "-Fn 1",
                file_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if self.process.stdout is None:
                logger.error("Failed to access log")
                return

            logger.info(f"Tailing log file: {file_path}")
            async for line in self.process.stdout:
                decoded_line = line.decode("utf-8").strip()
                await self.line_callback(decoded_line)

        except asyncio.CancelledError:
            logger.debug(f"Task cancelled for: {file_path}")
        finally:
            if self.process:
                try:
                    logger.debug(self.process)
                    self.process.terminate()
                    await self.process.wait()
                    logger.debug("Terminated old process.")
                except ProcessLookupError:
                    logger.debug("Process already stopped")

    async def watch_log(
        self,
    ):
        """Will tail log, watch the file name, and update tail if the log
        file name changes when program making the log restarts. Use this
        if the log filename changes on restarts."""
        while True:
            log_files = glob.glob(
                os.path.join(self.log_directory, self.log_file_pattern)
            )
            if log_files:
                # If there are ever more than one log file this will select newest
                latest_log_file = max(log_files, key=os.path.getctime)

                if latest_log_file != self.current_log_file:
                    logger.info(f"New log file detected: {latest_log_file}")

                    if self.current_task:
                        self.current_task.cancel()
                        try:
                            await self.current_task
                        except asyncio.CancelledError:
                            logger.debug(f"Task cancelled for: {self.current_log_file}")

                    self.current_log_file = latest_log_file
                    self.current_task = asyncio.create_task(
                        self.tail_log(self.current_log_file)
                    )
            else:
                logger.warning("No log file, server restarting? Waiting for fresh log file...")

            await asyncio.sleep(5)

    async def start(self):
        """Start watching the log."""
        log_files = glob.glob(os.path.join(self.log_directory, self.log_file_pattern))

        if log_files:
            latest_log_file = max(log_files, key=os.path.getctime)
        else:
            logger.warning("No log file.")
            return

        # I really only want to look for * in my case
        glob_chars = ["*", "?", "[", "]"]
        has_glob_chars = any([True for g in glob_chars if g in self.log_file_pattern])
        if has_glob_chars:
            await self.watch_log()
        else:
            asyncio.create_task(self.tail_log(latest_log_file))
