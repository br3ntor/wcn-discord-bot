import asyncio

import discord

from src.config import Config
from src.services.pz_server import pz_send_message
from src.services.server import restart_zomboid_server, server_isrunning

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES

countdown_isrunning = {server: False for server in SYSTEM_USERS.values()}
abort_signal = {"aborted": False}


class AutoRestart:
    """
    Handles server auto-restart with countdown timer and Discord announcements.
    """

    def __init__(self):
        pass

    async def run_countdown(self, system_user: str, duration: int) -> tuple[bool, str]:
        """
        Runs a countdown timer for the auto-restart, announcing the time remaining
        to the Project Zomboid server every minute.

        Args:
            system_user: The linux user running the server.
            duration: Time in seconds. Should be a multiple of 60.
        Returns:
            tuple[bool, str]: Success (True) or failure (False), and error message.
        """
        server_name = SERVER_NAMES[system_user]

        if countdown_isrunning[system_user]:
            return (
                False,
                f"There is already a countdown running for **{server_name}** server.",
            )
        if abort_signal["aborted"]:
            return False, f"Countdown abort in progress for **{server_name}** server."

        countdown_isrunning[system_user] = True
        seconds_left = duration
        while seconds_left > 0:
            if abort_signal["aborted"]:
                countdown_isrunning[system_user] = False

                if not any(countdown_isrunning.values()):
                    abort_signal["aborted"] = False

                await pz_send_message(system_user, "Restart has been ABORTED")

                return False, f"Auto restart ABORTED for the **{server_name}** server."

            if seconds_left % 60 == 0:
                await pz_send_message(
                    system_user,
                    f"The server will restart in {seconds_left//60} minute(s)!",
                )

            await asyncio.sleep(5)
            seconds_left -= 5
        countdown_isrunning[system_user] = True
        return True, ""

    async def restart_server(self, system_user: str) -> bool:
        """Restarts the Project Zomboid game-server."""
        return await restart_zomboid_server(system_user)

    async def auto_restart(self, channel: discord.TextChannel, server_name: str, init_msg: str) -> bool:
        """
        Starts a countdown and restarts a server at the end of it.

        Args:
            channel: Discord channel to send messages to.
            server_name: The server name (key in SERVER_NAMES).
            init_msg: Initial message to announce countdown start.
        Returns:
            bool: True if restart succeeded, False otherwise.
        """
        system_user = SYSTEM_USERS[server_name]

        is_running = await server_isrunning(system_user)
        if not is_running:
            await channel.send(
                f"Auto restart failed, **{server_name}** is **NOT** running!"
            )
            return False

        await channel.send(init_msg)

        countdown_status = await self.run_countdown(system_user, 300)
        if not countdown_status[0]:
            await channel.send(countdown_status[1])
            return False

        if not await self.restart_server(system_user):
            await channel.send(
                f"There was a problem restarting the **{server_name}** server."
            )
            return False

        msg = f"Success! The **{server_name}** was restarted and is now loading back up."
        await channel.send(msg)
        return True


auto_restart = AutoRestart()
