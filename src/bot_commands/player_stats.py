import logging
from datetime import datetime, timezone

import discord
from discord import app_commands

from src.config import Config
from src.services.bot_db import get_player_command_counts_by_character, get_server_world_start
from src.utils.helpers import make_player_autocomplete
from src.utils.player_lookup import lookup_player

logger = logging.getLogger(__name__)

SYSTEM_USERS = Config.SYSTEM_USERS
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID
SERVER_NAMES = Config.SERVER_NAMES


def _relative_time(dt: datetime) -> str:
    delta = datetime.now(timezone.utc) - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''} ago"
    weeks = days // 7
    if weeks < 4:
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


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

    world_start = await get_server_world_start(server.name)

    character_counts = await get_player_command_counts_by_character(steam_id, server.name)

    if not character_counts:
        await interaction.followup.send(
            f"No command stats found for **{player_name}** ({steam_id}) on **{server.name}**."
        )
        return

    if world_start:
        header = (
            f"**{steam_id}** on **{server.name}** — "
            f"since {world_start.strftime('%B %d, %Y')} ({_relative_time(world_start)})"
        )
    else:
        header = f"**{steam_id}** on **{server.name}** — *current world*"
    lines = [header]
    for char_name in sorted(character_counts, key=str.casefold):
        counts = character_counts[char_name]
        heals_admin = counts.get("heal_player", 0)
        heals_self = counts.get("heal_self", 0)
        restores_admin = counts.get("restore_levels", 0)
        restores_self = counts.get("restore_self", 0)

        heals_total = heals_admin + heals_self
        restores_total = restores_admin + restores_self

        parts = [f"**{char_name}**:"]
        if heals_total:
            parts.append(
                f"{heals_total} heal{'s' if heals_total != 1 else ''}"
                f" ({heals_admin} admin, {heals_self} self)"
            )
        else:
            parts.append("0 heals")
        if restores_total:
            parts.append(
                f"{restores_total} restore{'s' if restores_total != 1 else ''}"
                f" ({restores_admin} admin, {restores_self} self)"
            )
        else:
            parts.append("0 restores")

        lines.append("  ".join(parts))

    await interaction.followup.send("\n".join(lines))
