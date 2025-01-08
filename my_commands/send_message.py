import asyncio
import re

import discord
from discord import app_commands

from config import Config
from utils.server_helpers import server_isrunning

SERVER_NAMES = Config.SERVER_NAMES
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES)
    ]
)
@app_commands.describe(
    server="Which server should recieve this message?",
    message="What would you like to say?",
)
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def send_message(
    interaction: discord.Interaction, server: app_commands.Choice[int], message: str
):
    """Send a message to everyone in the server."""
    await interaction.response.defer()

    system_user = SERVER_NAMES[server.name]

    # Check if game server is running before we try and use it
    is_running = await server_isrunning(system_user)
    if not is_running:
        await interaction.followup.send(f"{server.name} is **NOT** running!")
        return

    # Send command and respond to result
    valid_msg = re.sub(r"[^a-zA-Z!?\s\d]", "", message)
    server_msg = f'servermsg "{valid_msg}"'
    cmd = [
        "runuser",
        system_user,
        "-c",
        f"/home/{system_user}/pzserver send '{server_msg}'",
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
