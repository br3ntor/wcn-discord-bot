import asyncio
import re

import discord
from discord import app_commands

from config import SERVER_NAMES
from utils.db_helpers import get_admins, get_user

admin_group = app_commands.Group(
    name="admin", description="Commands to control in-game accesslevel."
)


@admin_group.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES)
    ],
    accesslevel=[
        app_commands.Choice(name="Give admin", value=1),
        app_commands.Choice(name="Remove admin", value=2),
    ],
)
@app_commands.describe(
    server="Which server?",
    accesslevel="The choice to give or take admin",
    player="The name of the player in game.",
)
async def toggle(
    interaction: discord.Interaction,
    server: app_commands.Choice[int],
    accesslevel: app_commands.Choice[int],
    player: str,
):
    """Give or remove admin powers."""
    if re.search(r"[\"']", player):
        await interaction.response.send_message("Quotes not allowed.")
        return

    # Should be called before the first db call
    await interaction.response.defer()

    the_user = await get_user(server.name, player)
    if not the_user:
        await interaction.followup.send(
            f"username: **{player}** not found in **{server.name}** database"
        )
        return
    elif isinstance(the_user, str):
        await interaction.followup.send(the_user)
        return

    access_level = "admin" if accesslevel.value == 1 else "none"
    server_msg = f'setaccesslevel "{player}" {access_level}'
    cmd = [
        "runuser",
        f"{SERVER_NAMES[server.name]}",
        "-c",
        f"/home/{SERVER_NAMES[server.name]}/pzserver send '{server_msg}'",
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )

        # Get the output of the subprocess.
        output, error = await process.communicate()

    except Exception as e:
        print(f"Subprocess error occurred: {e}")

    print(output.decode())
    print(error.decode())

    status = (
        f"**{player}** accesslevel has been set to **{access_level}** "
        f"on the **{server.name}** server"
        if "OK" in output.decode()
        else "Something wrong maybe\n" + output.decode()
    )

    await interaction.followup.send(status)


@admin_group.command()
async def list(interaction: discord.Interaction):
    """Get a list of admins on a zomboid server."""
    the_boys = [
        f"**{servername} Admins**:\n{await get_admins(username)}"
        for servername, username in SERVER_NAMES.items()
    ]
    formatted_msg = "\n".join(the_boys)
    await interaction.response.send_message(formatted_msg)
