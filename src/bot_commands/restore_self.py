import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands

from src.config import Config
from src.features.skill_restore import LevelRestore
from src.services.bot_db import (
    get_player_command_cooldown,
    log_command_history,
    record_player_command_use,
)
from src.services.pocketbase import pb_client
from src.services.pz_server import pz_players
from src.utils.player_lookup import is_valid_steam_id, lookup_player

logger = logging.getLogger(__name__)

SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES
COMMAND_NAME = "restore_self"
COOLDOWN = timedelta(days=30)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_remaining(until: datetime, now: datetime) -> str:
    seconds = max(1, int((until - now).total_seconds()))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)

    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes or not parts:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return ", ".join(parts)


@app_commands.command(
    name="restore-self",
    description="Restore your linked player's skill levels on a game server.",
)
@app_commands.choices(
    server=[
        app_commands.Choice(name=server_name, value=index + 1)
        for index, server_name in enumerate(SERVER_NAMES.values())
    ]
)
@app_commands.describe(server="Which server?")
async def restore_self(
    interaction: discord.Interaction, server: app_commands.Choice[int]
):
    """Restore the caller's linked player if they are online and off cooldown."""
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

    try:
        cooldown = await get_player_command_cooldown(
            steam_id, server_name, COMMAND_NAME
        )
    except Exception as e:
        logger.error("Could not read self-restore cooldown: %s", e)
        await interaction.followup.send(
            "The self-restore cooldown could not be checked. Please try again later."
        )
        return

    now = datetime.now(timezone.utc)
    if cooldown:
        try:
            cooldown_until = _parse_utc(cooldown["cooldown_until"])
        except (KeyError, TypeError, ValueError):
            logger.exception(
                "Invalid cooldown record for %s on %s", steam_id, server_name
            )
            await interaction.followup.send(
                "Your self-restore cooldown record is invalid. Please contact an administrator."
            )
            return

        if cooldown_until > now:
            await interaction.followup.send(
                "Your self-restore is on cooldown for **"
                f"{_format_remaining(cooldown_until, now)}** on **{server_name}**."
            )
            return

    resolved_steam_id, player_name, lookup_error = await lookup_player(
        system_user, steam_id
    )
    if lookup_error or not resolved_steam_id or not player_name:
        await interaction.followup.send(
            lookup_error
            or f"Your linked player is not registered on the **{server_name}** server."
        )
        return

    online_players = await pz_players(system_user)
    if online_players is None:
        await interaction.followup.send(
            f"I could not check whether your player is online on **{server_name}**."
        )
        return

    online_name = next(
        (
            online_player
            for online_player in online_players
            if online_player.casefold() == player_name.casefold()
        ),
        None,
    )
    if online_name is None:
        await interaction.followup.send(
            f"Your linked player **{player_name}** is not currently online on **{server_name}**."
        )
        return

    lr = LevelRestore(server_name, online_name)
    result = await lr.restore_levels()
    if not result:
        await interaction.followup.send(
            f"Level restore failed for **{online_name}** on the **{server_name}** "
            "server. Make sure you have a valid death record within the last few "
            "days. Please contact an administrator if the problem persists."
        )
        return

    cooldown_recorded = await record_player_command_use(
        steam_id=steam_id,
        server_name=server_name,
        command_name=COMMAND_NAME,
        cooldown_until=datetime.now(timezone.utc) + COOLDOWN,
    )
    if not cooldown_recorded:
        logger.error(
            "Self-restore succeeded but cooldown could not be recorded for %s on %s",
            steam_id,
            server_name,
        )
        await interaction.followup.send(
            f"I restored skill levels for **{online_name}** on **{server_name}**, "
            "but could not record the cooldown. Please contact an administrator."
        )
        return

    await interaction.followup.send(
        f"I restored skill levels for 🔄 **{online_name}** on the **{server_name}** server."
    )

    await log_command_history(
        interaction,
        COMMAND_NAME,
        server_name=server_name,
        steam_id=steam_id,
        player_name=online_name,
        arguments={"server": server_name},
    )
