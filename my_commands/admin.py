import re

import discord
from discord import app_commands

from config import Config
from lib.db import get_admins, get_player
from lib.pzserver import pz_send_command
from lib.server_utils import server_isrunning

SERVER_NAMES = Config.SERVER_NAMES
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID

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
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
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

    # Check for existence of player in game servers database
    system_user = SERVER_NAMES[server.name]
    player_row = await get_player(system_user, player)
    if not player_row:
        await interaction.followup.send(
            f"username: **{player}** not found in **{server.name}** database"
        )
        return
    # NOTE: If player_row is a str I think it's an error msg, maybe theres a clearer way to do this
    elif isinstance(player_row, str):
        await interaction.followup.send(player_row)
        return

    # Make sure server is running befor sending command
    is_running = await server_isrunning(system_user)
    if not is_running:
        await interaction.followup.send(f"{server.name} is **NOT** running!")
        return

    access_level = "admin" if accesslevel.value == 1 else "none"
    server_msg = f'setaccesslevel "{player}" {access_level}'
    result = await pz_send_command(system_user, server_msg)

    status = (
        f"**{player}** accesslevel has been set to **{access_level}** "
        f"on the **{server.name}** server"
        if result
        else "Something wrong maybe, see logs"
    )

    await interaction.followup.send(status)


@admin_group.command()
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def list(interaction: discord.Interaction):
    """Get a list of admins on a zomboid server."""
    the_boys = [
        f"**{servername} Admins**:\n{await get_admins(username)}"
        for servername, username in SERVER_NAMES.items()
    ]
    formatted_msg = "\n\n".join(the_boys)
    await interaction.response.send_message(formatted_msg)
