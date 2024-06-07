import asyncio
import os
import re

import discord
from discord import app_commands

from config import REMOTE_SERVER_IP, SERVER_DATA
from utils.server_helpers import server_isrunning

MOD_ROLE_ID = int(os.getenv("MOD_ROLE_ID", 0))

ENABLED_SERVERS = [
    server["name"] for server in SERVER_DATA if server["ip"] == REMOTE_SERVER_IP
]


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(ENABLED_SERVERS)
    ]
)
@app_commands.describe(
    server="Which server should recieve this message?",
    message="What would you like to say?",
)
async def send_message(
    interaction: discord.Interaction, server: app_commands.Choice[int], message: str
):
    """Send a message to everyone in the server."""

    # Only discord mods can use the command
    # This gets taken care of when setuping up bot but its nice to have still
    # Oh also the framwork has a special check function to do this already I should use
    assert isinstance(interaction.user, discord.Member)
    if interaction.user.get_role(MOD_ROLE_ID) is None:
        await interaction.response.send_message("You are not worthy.", ephemeral=True)
        return

    # This def needs to be called before doing work that takes time,
    # but I wonder if it may as well be first line of the function?
    await interaction.response.defer()

    is_running = await server_isrunning(server.name)
    if not is_running:
        await interaction.followup.send(f"{server.name} is **NOT** running!")
        return

    # Send command and respond to result
    valid_msg = re.sub(r"[^a-zA-Z!?\s\d]", "", message)
    server_msg = f'servermsg "{valid_msg}"'
    cmd = [
        "runuser",
        f"{server.name}",
        "-c",
        f"/home/{server.name}/pzserver send '{server_msg}'",
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )

        # # Get the output of the subprocess.
        output, error = await process.communicate()

    except Exception as e:
        print(f"Subprocess error occurred: {e}")

    # This outputs to systemd journal logs as byte data still?
    print(output.decode())
    print(error.decode())

    status = (
        f"Message sent to **{server.name}** server:\n> {message}"
        if "OK" in output.decode()
        else "Something wrong maybe\n" + output.decode()
    )

    await interaction.followup.send(status)
