import asyncio
import subprocess
import time
from typing import Callable, Coroutine

from config import Config
from lib.db import get_player
from lib.pzserver import pz_heal_player, pz_send_command

SERVER_NAMES = Config.SERVER_NAMES
SYSTEM_USERS = Config.SYSTEM_USERS


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
        """Verify godmode was applied and removed by watching for the correct
        sequence of log lines."""
        if f"User {self.player_name} is now invincible." in log_line:
            self.godmode_on = True
        if f"User {self.player_name} is no more invincible." in log_line:
            if self.godmode_on:
                print(f"Godmode was given and taken away for {self.player_name}.")
                return True
            print("Godmode was taken away but not given? Maybe admin.")
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

    async def gogo_godmode(self):
        """Guaranteed to work godmode!"""
        # Makes sure player has no accesslevel
        player_row = await get_player(SYSTEM_USERS[self.server_name], self.player_name)
        if player_row and player_row[13]:
            print("Accesslevel:", player_row[13])
            print("No reason to use this on immortals.")
            return False

        # This is going to start off listenting to log and scanning log lines
        # until it finds the player online or runs out of players to check.
        check_if_online = asyncio.create_task(
            self.log_watcher(self.verify_player_online)
        )
        await pz_send_command(SYSTEM_USERS[self.server_name], "players")

        is_online = await check_if_online
        if not is_online:
            return False

        # Now that we know player is online, we watch for logs to confirm
        # Godmode was given and taken away.
        check_if_healed = asyncio.create_task(
            self.log_watcher(self.verify_player_healed)
        )
        await pz_heal_player(SYSTEM_USERS[self.server_name], self.player_name)

        is_healed = await check_if_healed
        if not is_healed:
            return False

        return True
