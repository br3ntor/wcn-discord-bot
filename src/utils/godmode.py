import asyncio
import subprocess
import time
from typing import Callable, Coroutine

from src.config import Config
from src.utils.game_db import get_player
from src.utils.pzserver import pz42_heal_player, pz_heal_player, pz_send_command
from src.utils.server_utils import get_game_version

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
            print("players command recieved!")
            self.players_command_received = True
            return None

        # This assumes there will never be a break between previous line and playerlist
        if self.players_command_received:
            # This seems to happen when no players or end of playerlist
            if len(log_line) == 0:
                print("No players or end of list.")
                return False
            if log_line[0] == "-":
                if f"{self.player_name}" in log_line:
                    print("player found!")
                    return True
                return None
            print("Unexpected log line.")
            return False

    async def verify_player_healed(self, log_line: str) -> bool | None:
        # 1. Track activation
        if f"User {self.player_name} is now invincible." in log_line:
            self.godmode_on = True
            return None

        # 2. Track deactivation (Check both version strings)
        off_strings = [
            f"User {self.player_name} is no more invincible.",  # B41
            f"User {self.player_name} is no longer invincible.",  # B42
        ]

        if any(s in log_line for s in off_strings):
            if self.godmode_on:
                print(f"Godmode was given and taken away for {self.player_name}.")
            else:
                print("Godmode was taken away but not given? Maybe admin.")

            self.godmode_on = False  # Reset state
            return True

    async def log_watcher(
        self,
        log_handler: Callable[[str], Coroutine[None, None, bool | None]],
    ):
        """Watches log lines with tail and runs a callback on each line."""
        try:
            process = await asyncio.create_subprocess_exec(
                "tail",
                "-fn 1",
                self.log_file_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if process.stdout is None:
                print("Failed to access log")
                return False

            print(f"Tailing log file: {self.log_file_path}")
            start_time = time.time()
            async for line in process.stdout:
                decoded_line = line.decode("utf-8").strip()
                print(decoded_line)  # log line
                result = await log_handler(decoded_line)
                if result is None:
                    elapsed_time = time.time() - start_time
                    print(f"Elapsed Watch Time: {elapsed_time}")
                    if elapsed_time > 5:
                        print("Watcher timed out, you are really dumb.")
                        return False
                    continue
                if result:
                    return True

                print("Log handler failed")
                return False

            # I don't think it will ever be possible to get here since it would mean
            # we've exhausted all log lines which will never happen as long as pz server is running.
            return False
        except asyncio.CancelledError:
            print(f"TL:Task cancelled for: {self.log_file_path}")
            return False
        finally:
            if process:
                try:
                    print(process)
                    process.terminate()
                    await process.wait()
                    print("Terminated old process.")
                except ProcessLookupError:
                    print("ProcessLookupError occurred, process already stopped?")

    async def gogo_godmode(self) -> bool:
        """Guaranteed to work godmode by verifying state transitions via logs."""

        # 1. Initialize Version Config
        version = get_game_version(SYSTEM_USERS[self.server_name])
        config = VERSION_CONFIG.get(version)

        if not config:
            print(f"Error: Unsupported game version '{version}'")
            return False

        # 2. Explicit Permission Check
        # We only want to run this on 'normal' players (non-admins)
        player_row = await get_player(SYSTEM_USERS[self.server_name], self.player_name)

        if not player_row:
            print(f"Player {self.player_name} not found in database.")
            return False

        raw_access = player_row[config["access_idx"]]
        if not config["is_normal_player"](raw_access):
            print(
                f"Accesslevel '{raw_access}' detected. No reason to use this on immortals."
            )
            return False

        # 3. Verify Player is Online
        # We start the listener BEFORE sending the command to capture the response
        check_online_task = asyncio.create_task(
            self.log_watcher(self.verify_player_online)
        )
        await pz_send_command(SYSTEM_USERS[self.server_name], "players")

        if not await check_online_task:
            print(f"Abort: {self.player_name} is not currently online.")
            return False

        # 4. Apply Godmode/Heal and Verify via Logs
        check_healed_task = asyncio.create_task(
            self.log_watcher(self.verify_player_healed)
        )

        # Execute the version-specific heal command
        await config["heal_func"](SYSTEM_USERS[self.server_name], self.player_name)

        # Wait for verify_player_healed to confirm the "invincible" log sequence
        is_healed = await check_healed_task

        if is_healed:
            print(f"Successfully verified healing sequence for {self.player_name}.")
            return True

        print(f"Failed to verify healing sequence for {self.player_name}.")
        return False
