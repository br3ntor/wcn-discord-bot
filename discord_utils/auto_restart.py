import asyncio

import discord

from config import Config
from lib.pzserver import pz_send_message
from lib.server_utils import server_isrunning

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
SERVER_NAMES = Config.SERVER_NAMES

# Track if countdown timer is running
countdown_isrunning = {server: False for server in SERVER_NAMES}

# Will abort all running countdowns
abort_signal = {"aborted": False}


async def auto_restart_server(channel: discord.TextChannel, server_name: str):
    """Takes the display name which will lookup system_user from SERVER_NAMES"""
    global abort_signal, countdown_isrunning
    if countdown_isrunning[server_name]:
        print(f"There is already a countdown running for **{server_name}** server.")
        return

    if abort_signal["aborted"]:
        print(f"Countdown abortion in progress for **{server_name}** server.")
        return

    system_user = SERVER_NAMES[server_name]

    is_running = await server_isrunning(system_user)
    if not is_running:
        print("Auto restart task will not start since the server is not running.")
        return

    await channel.send(
        f"Auto restart triggered for the **{server_name}** server. Restarting in 5min."
    )

    # Start tracking running countdowns
    countdown_isrunning[server_name] = True
    seconds_left = 300
    while seconds_left > 0:
        if abort_signal["aborted"]:
            countdown_isrunning[server_name] = False
            abort_signal["aborted"] = False
            await channel.send(
                f"Auto restart ABORTED 👼 for the **{server_name}** server."
            )
            await pz_send_message(SERVER_NAMES[server_name], "Restart has been ABORTED")
            return

        # Here we send restart msg to game server every minute
        if seconds_left % 60 == 0:
            await pz_send_message(
                system_user,
                f"The server will restart in {seconds_left//60} minute(s)!",
            )

        await asyncio.sleep(5)
        seconds_left -= 5

    # This could be its own function in lib/server_utils
    try:
        cmd = [
            "sudo",
            "/usr/bin/systemctl",
            "restart",
            system_user,
        ]
        process = await asyncio.create_subprocess_exec(*cmd)
        await process.wait()

    except Exception as e:
        print(f"error occurred: {e}")

    restart_msg = (
        f"Success! The **{server_name}** was restarted and is now loading back up."
    )
    await channel.send(restart_msg)
    countdown_isrunning[server_name] = False
