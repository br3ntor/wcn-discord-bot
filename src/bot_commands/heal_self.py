import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands

from src.config import Config
from src.services.bot_db import (
    get_latest_player_command,
    log_command_history,
)
from src.services.game_db import gamedb_get_players_by_steamid
from src.services.pocketbase import pb_client
from src.services.pz_server import pz_heal_player, pz_players
from src.utils.helpers import format_remaining
from src.utils.player_lookup import is_valid_steam_id

logger = logging.getLogger(__name__)

SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES
COMMAND_NAME = "heal_self"
COOLDOWN = timedelta(days=15)


@app_commands.command(
    name="heal_self", description="Heal your linked player on a game server."
)
@app_commands.choices(
    server=[
        app_commands.Choice(name=server_name, value=index + 1)
        for index, server_name in enumerate(SERVER_NAMES.values())
    ]
)
@app_commands.describe(server="Which server?")
async def heal_self(interaction: discord.Interaction, server: app_commands.Choice[int]):
    """Heal the caller's linked player if they are online and off cooldown."""
    await interaction.response.defer(ephemeral=True)

    discord_id = str(interaction.user.id)
    link_ok, player_link = await pb_client.find_player_link("discord_id", discord_id)
    if not link_ok:
        await interaction.followup.send(
            "Player linking is temporarily unavailable because the central database "
            "could not be reached."
        )
        return

    if not player_link:
        await interaction.followup.send(
            "You do not have a linked player. Use `/link` to link your Discord "
            "account first."
        )
        return

    steam_id = player_link.get("steam_id")
    if not isinstance(steam_id, str) or not is_valid_steam_id(steam_id):
        logger.error("Player link for Discord %s has an invalid Steam ID", discord_id)
        await interaction.followup.send(
            "Your player link is invalid. Please contact an administrator."
        )
        return

    server_name = server.name
    system_user = SYSTEM_USERS.get(server_name)
    if not system_user:
        await interaction.followup.send("That game server is not configured.")
        return

    whitelist_rows = await gamedb_get_players_by_steamid(system_user, steam_id)
    if isinstance(whitelist_rows, str):
        await interaction.followup.send(
            f"Could not look up your characters on **{server_name}**: {whitelist_rows}"
        )
        return
    if not whitelist_rows:
        await interaction.followup.send(
            f"Your linked Steam account is not registered on **{server_name}**."
        )
        return

    whitelist_names = [row[2] for row in whitelist_rows]

    online_players = await pz_players(system_user)
    if online_players is None:
        await interaction.followup.send(
            f"I could not check whether your player is online on **{server_name}**."
        )
        return

    online_name = next(
        (
            player
            for player in online_players
            if player.casefold() in (name.casefold() for name in whitelist_names)
        ),
        None,
    )
    if online_name is None:
        await interaction.followup.send(
            f"None of your linked characters are currently online on **{server_name}**."
        )
        return

    try:
        latest = await get_latest_player_command(
            steam_id, server_name, COMMAND_NAME, online_name
        )
    except Exception as e:
        logger.error("Could not read self-heal history: %s", e)
        await interaction.followup.send(
            "The self-heal cooldown could not be checked. Please try again later."
        )
        return

    now = datetime.now(timezone.utc)
    if latest is not None:
        cooldown_until = latest + COOLDOWN
        if cooldown_until > now:
            await interaction.followup.send(
                "Your self-heal is on cooldown for **"
                f"{format_remaining(cooldown_until, now)}** on **{server_name}**."
            )
            return

    result, message = await pz_heal_player(system_user, online_name)
    if not result:
        await interaction.followup.send(f"Heal failed for **{online_name}**: {message}")
        return

    await interaction.followup.send(
        f"I healed 💖 **{online_name}** on the **{server_name}** server."
    )

    await log_command_history(
        interaction,
        COMMAND_NAME,
        server_name=server_name,
        steam_id=steam_id,
        player_name=online_name,
        arguments={"server": server_name},
    )
