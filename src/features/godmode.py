import asyncio
import logging
import subprocess
import time
from typing import Callable, Coroutine

from src.config import Config
from src.services.game_db import get_player
from src.services.pz_server import pz42_heal_player, pz_heal_player, pz_send_command
from src.services.server import get_game_version

logger = logging.getLogger(__name__)

SERVER_NAMES = Config.SERVER_NAMES
SYSTEM_USERS = Config.SYSTEM_USERS

VERSION_CONFIG = {
    "B41": {
        "access_idx": 13,
        "is_normal_player": lambda val: val is None or str(val).strip() == "",
        "heal_func": pz_heal_player,
    },
    "B42": {
        "access_idx": 5,
        "is_normal_player": lambda val: str(val) == "2",
        "heal_func": pz42_heal_player,
    },
}


class GodMode:
    """
    Toggles godmode on a player after verifying they are online and
    verifies command was applied and removed successfully.
    """

    def __init__(self, server_name: str, player_name: str) -> None:
        self.server_name = server_name
        self.player_name = player_name
        self.players_command_received = False
        self.godmode_on = False
        self.log_file_path = (
            f"/home/{SYSTEM_USERS[server_name]}/log/console/pzserver-console.log"
        )

    async def verify_player_online(self, log_line: str) -> bool | None:
        """Monitor the log for the correct sequence of lines to confirm player
        is online and the commands send to the server execute correctly."""
        if "Players connected" in log_line:
            logger.info("players command recieved!")
            self.players_command_received = True
            return None

        if self.players_command_received:
            if len(log_line) == 0:
                logger.info("No players or end of list.")
                return False
            if log_line[0] == "-":
                if f"{self.player_name}" in log_line:
                    logger.info("player found!")
                    return True
                return None
            logger.warning("Unexpected log line.")
            return False

    async def verify_player_healed(self, log_line: str) -> bool | None:
        if f"User {self.player_name} is now invincible." in log_line:
            self.godmode_on = True
            return None

        off_strings = [
            f"User {self.player_name} is no more invincible.",
            f"User {self.player_name} is no longer invincible.",
        ]

        if any(s in log_line for s in off_strings):
            if self.godmode_on:
                logger.info(f"Godmode was given and taken away for {self.player_name}.")
            else:
                logger.warning("Godmode was taken away but not given? Maybe admin.")

            self.godmode_on = False
            return True

    async def log_watcher(
        self,
        log_handler: Callable[[str], Coroutine[None, None, bool | None]],
    ):
        """Watches log lines with tail and runs a callback on each line."""
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "tail",
                "-fn 1",
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
                    logger.info(f"Elapsed Watch Time: {elapsed_time}")
                    if elapsed_time > 5:
                        logger.warning("Watcher timed out, you are really dumb.")
                        return False
                    continue
                if result:
                    return True

                logger.error("Log handler failed")
                return False

            return False
        except asyncio.CancelledError:
            logger.info(f"TL:Task cancelled for: {self.log_file_path}")
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

    async def gogo_godmode(self) -> bool:
        """Guaranteed to work godmode by verifying state transitions via logs."""

        version = get_game_version(SYSTEM_USERS[self.server_name])
        config = VERSION_CONFIG.get(version)

        if not config:
            logger.error(f"Error: Unsupported game version '{version}'")
            return False

        player_row = await get_player(SYSTEM_USERS[self.server_name], self.player_name)

        if not player_row:
            logger.warning(f"Player {self.player_name} not found in database.")
            return False

        raw_access = player_row[config["access_idx"]]
        if not config["is_normal_player"](raw_access):
            logger.warning(
                f"Accesslevel '{raw_access}' detected. No reason to use this on immortals."
            )
            return False

        check_online_task = asyncio.create_task(
            self.log_watcher(self.verify_player_online)
        )
        await pz_send_command(SYSTEM_USERS[self.server_name], "players")

        if not await check_online_task:
            logger.warning(f"Abort: {self.player_name} is not currently online.")
            return False

        check_healed_task = asyncio.create_task(
            self.log_watcher(self.verify_player_healed)
        )

        await config["heal_func"](SYSTEM_USERS[self.server_name], self.player_name)

        is_healed = await check_healed_task

        if is_healed:
            logger.info(f"Successfully verified healing sequence for {self.player_name}.")
            return True

            logger.error(f"Failed to verify healing sequence for {self.player_name}.")
        return False
