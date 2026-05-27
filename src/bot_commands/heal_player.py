import logging

import discord
from discord import app_commands

from src.config import Config
from src.services.bot_db import get_player_stats, record_command_use
from src.services.pz_server import pz_heal_player
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
@app_commands.describe(server="Which server?", player="Who will you save?")
@app_commands.autocomplete(player=make_player_autocomplete())
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def heal_player(
    interaction: discord.Interaction, server: app_commands.Choice[int], player: str
):
    """Heals a player by toggling godmode on and off."""
    await interaction.response.defer()
    result, message = await pz_heal_player(SYSTEM_USERS[server.name], player)
    if result:
        stats_msg = ""
        try:
            steam_id, _, _ = await lookup_player(SYSTEM_USERS[server.name], player)
            if steam_id:
                await record_command_use(steam_id, server.name, player, "heal")
                stats = await get_player_stats(steam_id)
                if stats:
                    stats_msg = f" (Healed {stats[0]} time{'s' if stats[0] != 1 else ''} total)"
        except Exception as e:
            logger.warning(f"Failed to record heal stats: {e}")

        await interaction.followup.send(
            f"I have healed 💖 **{player}** on the **{server.name}** server!{stats_msg}"
        )
    else:
        await interaction.followup.send(f"Heal failed for **{player}**: {message}")
