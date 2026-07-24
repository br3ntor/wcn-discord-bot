import logging

import discord
from discord import app_commands

from src.config import Config
from src.features.skill_restore import LevelRestore
from src.services.bot_db import get_player_command_counts_by_character, log_command_history
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
    server="Which server?", player="Player name to restore levels for"
)
@app_commands.autocomplete(player=make_player_autocomplete())
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def restore_levels(
    interaction: discord.Interaction, server: app_commands.Choice[int], player: str
):
    """Restores a player's skill levels to what they were before their most significant death."""
    await interaction.response.defer()

    lr = LevelRestore(server.name, player)
    result = await lr.restore_levels()

    if result:
        stats_msg = ""
        try:
            steam_id, _, _ = await lookup_player(SYSTEM_USERS[server.name], player)
            if steam_id:
                await log_command_history(
                    interaction,
                    "restore_levels",
                    server_name=server.name,
                    steam_id=steam_id,
                    player_name=player,
                    arguments={"server": server.name, "player": player},
                )
                stats = await get_player_command_counts_by_character(steam_id, server.name)
                char_counts = stats.get(player, {})
                if char_counts:
                    heals_admin = char_counts.get("heal_player", 0)
                    heals_self = char_counts.get("heal_self", 0)
                    restores_admin = char_counts.get("restore_levels", 0)
                    restores_self = char_counts.get("restore_self", 0)
                    heals_total = heals_admin + heals_self
                    restores_total = restores_admin + restores_self
                    parts = [f"**{player}**:"]
                    parts.append(
                        f"{heals_total} heal{'s' if heals_total != 1 else ''}"
                        f" ({heals_admin} admin, {heals_self} self)"
                    )
                    parts.append(
                        f"{restores_total} restore{'s' if restores_total != 1 else ''}"
                        f" ({restores_admin} admin, {restores_self} self)"
                    )
                    stats_msg = "\n" + "  ".join(parts)
        except Exception as e:
            logger.warning(f"Failed to record restore stats: {e}")

        await interaction.followup.send(
            f"Successfully restored skill levels for **{player}** on the **{server.name}** server! 🔄{stats_msg}"
        )
    else:
        await interaction.followup.send(
            f"Level restore failed for **{player}** on the **{server.name}** server. "
            f"Make sure the player has a valid death record in the perk logs and can be targeted by RCON addxp. See console logs for details."
        )
