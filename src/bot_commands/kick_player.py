import re

import discord
from discord import app_commands

from src.config import Config
from src.services.pz_server import pz_kick_player
from src.services.server import server_isrunning

SYSTEM_USERS = Config.SYSTEM_USERS
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID
SERVER_NAMES = Config.SERVER_NAMES


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES.values())
    ]
)
@app_commands.describe(
    server="Which server?",
    player="The name of the player to kick.",
    reason="Reason for the kick (optional).",
)
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def kick_player(
    interaction: discord.Interaction,
    server: app_commands.Choice[int],
    player: str,
    reason: str | None = None,
):
    """Kicks a player from the server."""
    if re.search(r"[\"']", player):
        await interaction.response.send_message("Quotes not allowed.")
        return

    await interaction.response.defer()

    system_user = SYSTEM_USERS[server.name]

    if not await server_isrunning(system_user):
        await interaction.followup.send(f"**{server.name}** is **NOT** running!")
        return

    success, response = await pz_kick_player(system_user, player, reason)

    if success:
        reason_text = f" Reason: **{reason}**" if reason else ""
        await interaction.followup.send(
            f"**{player}** has been kicked from **{server.name}**.{reason_text}"
        )
    else:
        await interaction.followup.send(f"Failed to kick **{player}**: {response}")
