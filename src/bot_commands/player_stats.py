import logging

import discord
from discord import app_commands

from src.config import Config
from src.services.bot_db import get_player_stats
from src.utils.helpers import make_player_autocomplete
from src.utils.player_lookup import lookup_player

logger = logging.getLogger(__name__)

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
    server="Which server?", player="Player name to look up stats for"
)
@app_commands.autocomplete(player=make_player_autocomplete())
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def player_stats(
    interaction: discord.Interaction, server: app_commands.Choice[int], player: str
):
    """Shows how many times heal and restore levels have been used on a player."""
    await interaction.response.defer()

    steam_id, player_name, error = await lookup_player(
        SYSTEM_USERS[server.name], player
    )

    if error or not steam_id:
        await interaction.followup.send(error or f"Could not find player **{player}**.")
        return

    stats = await get_player_stats(steam_id)

    if stats:
        heals, restores = stats
        await interaction.followup.send(
            f"**{player_name}** ({steam_id})\n"
            f"Healed: {heals} time{'s' if heals != 1 else ''}\n"
            f"Levels Restored: {restores} time{'s' if restores != 1 else ''}"
        )
    else:
        await interaction.followup.send(
            f"No command stats found for **{player_name}** ({steam_id})."
        )
