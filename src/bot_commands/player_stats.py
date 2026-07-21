import logging

import discord
from discord import app_commands

from src.config import Config
from src.services.bot_db import get_player_command_counts
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
    """Shows heal and skill restore counts for a player, broken down by admin vs self."""
    await interaction.response.defer()

    steam_id, player_name, error = await lookup_player(
        SYSTEM_USERS[server.name], player
    )

    if error or not steam_id:
        await interaction.followup.send(error or f"Could not find player **{player}**.")
        return

    counts = await get_player_command_counts(steam_id)

    heals_admin = counts.get("heal_player", 0)
    heals_self = counts.get("heal_self", 0)
    restores_admin = counts.get("restore_levels", 0)
    restores_self = counts.get("restore_self", 0)

    heals_total = heals_admin + heals_self
    restores_total = restores_admin + restores_self

    if heals_total == 0 and restores_total == 0:
        await interaction.followup.send(
            f"No command stats found for **{player_name}** ({steam_id})."
        )
        return

    lines = [f"**{player_name}** ({steam_id})"]
    if heals_total:
        lines.append(
            f"Heals: {heals_total} total "
            f"({heals_admin} by admins, {heals_self} self)"
        )
    if restores_total:
        lines.append(
            f"Skill Restores: {restores_total} total "
            f"({restores_admin} by admins, {restores_self} self)"
        )

    await interaction.followup.send("\n".join(lines))
