"""Functions that use discord.py lib used in more than one command, task, webhook, etc."""

import discord

from config import Config
from lib.countdown import check_countdown_state, restart_countdown_timer
from lib.server_utils import restart_zomboid_server, server_isrunning

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
SYSTEM_USERS = Config.SYSTEM_USERS


async def auto_restart_server(
    channel: discord.TextChannel, server_name: str, init_msg: str
):
    """Starts a countdown and restarts a server at the end of it."""
    # FIX: This server_name / system_user is getting confusing, is there a better way? Perhaps with the type system?
    system_user = SYSTEM_USERS[server_name]

    # Counter must not be running or aborted
    counter_isready, err = check_countdown_state(system_user)
    if not counter_isready:
        await channel.send(err)
        return

    # Check if server is currently running
    is_running = await server_isrunning(system_user)
    if not is_running:
        await channel.send(
            f"Auto restart failed, **{server_name}** is **NOT** running!"
        )
        return

    # Announce that auto restart countdown has started
    await channel.send(init_msg)

    # Run the countdown
    countdown_completed = await restart_countdown_timer(system_user, 300)
    if not countdown_completed:
        await channel.send(f"Auto restart ABORTED 👼 for the **{server_name}** server.")
        return

    # Restarts the server after countdown has finished
    if not await restart_zomboid_server(system_user):
        await channel.send(
            f"There was a problem restarting the **{server_name}** server."
        )
        return

    msg = f"Success! The **{server_name}** was restarted and is now loading back up."
    await channel.send(msg)
