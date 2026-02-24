import asyncio
import logging
import subprocess
import time
from typing import Callable, Coroutine

from src.config import Config
from src.services.game_db import get_player
from src.services.pz_server import pz_send_command, pz_teleport_player

logger = logging.getLogger(__name__)

SERVER_NAMES = Config.SERVER_NAMES
SYSTEM_USERS = Config.SYSTEM_USERS


class Teleport:
    """
    Teleports one player to another after verifying both are online
    and confirming the teleport succeeded via server logs.
    """

    def __init__(self, server_name: str, player1: str, player2: str) -> None:
        self.server_name = server_name
        self.player1 = player1
        self.player2 = player2
        self.players_command_received = False
        self.player1_found = False
        self.player2_found = False
        self.teleport_successful = False
        self.log_file_path = (
            f"/home/{SYSTEM_USERS[server_name]}/log/console/pzserver-console.log"
        )

    async def verify_player_online(self, log_line: str) -> bool | None:
        """Monitor the log for the correct sequence of lines to confirm both players are online."""
        if "Players connected" in log_line:
            logger.info("Players command received!")
            self.players_command_received = True
            return None

        if self.players_command_received:
            if len(log_line) == 0:
                if not (self.player1_found and self.player2_found):
                    logger.info("No players or end of list.")
                    return False
                return None
            if log_line[0] == "-":
                if self.player1 in log_line:
                    logger.info(f"Found {self.player1}")
                    self.player1_found = True
                if self.player2 in log_line:
                    logger.info(f"Found {self.player2}")
                    self.player2_found = True
                if self.player1_found and self.player2_found:
                    logger.info(f"Both players found: {self.player1} and {self.player2}")
                    return True
                logger.info(f"Still need: {self.player2 if self.player1_found else self.player1}")
                return None
            logger.warning("Unexpected log line.")
            return False

    async def verify_teleport_success(self, log_line: str) -> bool | None:
        """Monitor the log for teleport success message."""
        teleport_phrase = f"teleported {self.player1} to {self.player2}"
        if teleport_phrase in log_line:
            logger.info(f"Teleport successful: {log_line}")
            self.teleport_successful = True
            return True
        return None

    async def log_watcher(
        self,
        log_handler: Callable[[str], Coroutine[None, None, bool | None]],
    ):
        """Watches log lines with tail and runs a callback on each line."""
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "tail",
                "-fn",
                "1",
                self.log_file_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if process.stdout is None:
                logger.error("Failed to access log")
                return False

            logger.info(f"Tailing log file: {self.log_file_path}")
            start_time = time.time()
            async for line in process.stdout:
                decoded_line = line.decode("utf-8").strip()
                logger.debug(decoded_line)
                result = await log_handler(decoded_line)
                if result is None:
                    elapsed_time = time.time() - start_time
                    logger.debug(f"Elapsed Watch Time: {elapsed_time}")
                    if elapsed_time > 10:
                        logger.warning("Watcher timed out")
                        return False
                    continue
                if result:
                    return True

                logger.error("Log handler failed")
                return False

            return False
        except asyncio.CancelledError:
            logger.info(f"Task cancelled for: {self.log_file_path}")
            return False
        finally:
            if process:
                try:
                    logger.debug(process)
                    process.terminate()
                    await process.wait()
                    logger.info("Terminated old process.")
                except ProcessLookupError:
                    logger.warning("ProcessLookupError occurred, process already stopped?")

    async def execute_teleport(self) -> bool:
        """Verifies both players are online, sends teleport command, and verifies success."""

        player1_row = await get_player(SYSTEM_USERS[self.server_name], self.player1)
        if not player1_row:
            logger.warning(f"Player {self.player1} not found in database.")
            return False

        player2_row = await get_player(SYSTEM_USERS[self.server_name], self.player2)
        if not player2_row:
            logger.warning(f"Player {self.player2} not found in database.")
            return False

        check_online_task = asyncio.create_task(
            self.log_watcher(self.verify_player_online)
        )
        await pz_send_command(SYSTEM_USERS[self.server_name], "players")

        if not await check_online_task:
            logger.warning(f"Abort: Both players must be online. {self.player1} and/or {self.player2} not found.")
            return False

        check_teleport_task = asyncio.create_task(
            self.log_watcher(self.verify_teleport_success)
        )

        await pz_teleport_player(
            SYSTEM_USERS[self.server_name], self.player1, self.player2
        )

        is_teleported = await check_teleport_task

        if is_teleported:
            logger.info(
                f"Successfully verified teleport of {self.player1} to {self.player2}."
            )
            return True

        logger.error(f"Failed to verify teleport of {self.player1} to {self.player2}.")
        return False
