import asyncio

import discord

from src.config import Config
from src.services.pz_server import pz_send_message
from src.services.server import restart_zomboid_server, server_isrunning

SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES


class AutoRestart:
    """
    Handles server auto-restart with countdown timer and Discord announcements.
    """

    def __init__(self):
        self._countdown_running = {server: False for server in SYSTEM_USERS.values()}
        self._abort_signals = {server: False for server in SYSTEM_USERS.values()}
        self._seconds_left = {server: 0 for server in SYSTEM_USERS.values()}

    def is_running(self, server_name: str) -> bool:
        """Check if a countdown is running for a server."""
        system_user = SYSTEM_USERS[server_name]
        return self._countdown_running[system_user]

    def remaining_seconds(self, server_name: str) -> int | None:
        """Seconds left on a running countdown, or None if none is running."""
        system_user = SYSTEM_USERS[server_name]
        if not self._countdown_running[system_user]:
            return None
        return self._seconds_left[system_user]

    def abort(self, server_name: str) -> None:
        """Set abort signal for a specific server."""
        system_user = SYSTEM_USERS[server_name]
        self._abort_signals[system_user] = True

    async def _run_countdown(
        self, system_user: str, duration: int
    ) -> tuple[bool, str]:
        """
        Runs a countdown timer for the auto-restart, announcing the time remaining
        to the Project Zomboid server every minute.

        Must only be called from `auto_restart`, which owns the countdown state.

        Args:
            system_user: The linux user running the server.
            duration: Time in seconds. Should be a multiple of 60.
        Returns:
            tuple[bool, str]: Success (True) or failure (False), and error message.
        """
        server_name = SERVER_NAMES[system_user]

        self._seconds_left[system_user] = duration
        while self._seconds_left[system_user] > 0:
            if self._abort_signals[system_user]:
                await pz_send_message(system_user, "Restart has been ABORTED")

                return (
                    False,
                    f"Auto restart ABORTED 👼 for the **{server_name}** server.",
                )

            if self._seconds_left[system_user] % 60 == 0:
                minutes = self._seconds_left[system_user] // 60
                await pz_send_message(
                    system_user,
                    f"The server will restart in {minutes} minute(s)!",
                )

            await asyncio.sleep(5)
            self._seconds_left[system_user] -= 5
        return True, ""

    async def auto_restart(
        self, channel: discord.TextChannel, server_name: str, init_msg: str
    ) -> bool:
        """
        Starts a countdown and restarts a server at the end of it.

        If a countdown is already running for the server, no new countdown is
        started — an acknowledgment with the remaining time is sent instead.

        Args:
            channel: Discord channel to send messages to.
            server_name: The server name (key in SERVER_NAMES).
            init_msg: Initial message to announce countdown start.
        Returns:
            bool: True if restart succeeded, False otherwise.
        """
        system_user = SYSTEM_USERS[server_name]

        if self.is_running(server_name):
            remaining = self.remaining_seconds(server_name) or 0
            minutes_left = max(1, round(remaining / 60))
            await channel.send(
                f"ℹ️ A restart for the **{server_name}** server is already "
                f"scheduled (~{minutes_left} min remaining)."
            )
            return False

        self._countdown_running[system_user] = True

        try:
            if not await server_isrunning(system_user):
                await channel.send(
                    f"Auto restart failed, **{server_name}** is **NOT** running!"
                )
                return False

            await channel.send(init_msg)

            countdown_status = await self._run_countdown(system_user, 300)
            if not countdown_status[0]:
                await channel.send(countdown_status[1])
                return False

            if not await restart_zomboid_server(system_user):
                await channel.send(
                    f"There was a problem restarting the **{server_name}** server."
                )
                return False

            msg = f"Success! The **{server_name}** was restarted and is now loading back up."
            await channel.send(msg)
            return True
        finally:
            self._countdown_running[system_user] = False
            self._seconds_left[system_user] = 0
            self._abort_signals[system_user] = False


auto_restart = AutoRestart()
