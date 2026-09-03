"""Whitelist account management cog for Discord bot."""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.config import Config
from src.services.game_db import gamedb_get_player_by_name
from src.services.pz_server import (
    pz_add_user,
    pz_remove_user,
    pz_reset_password_b41,
    pz_setpassword_b42,
)
from src.services.server import get_game_version, server_isrunning
from src.utils.helpers import generate_pz_password
from src.utils.player_lookup import (
    find_accounts_by_steamid,
    has_invalid_quotes,
    resolve_steam_id,
)

logger = logging.getLogger(__name__)

SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID
SERVER_CHOICES: list[app_commands.Choice[int]] = [
    app_commands.Choice(name=srv, value=index + 1)
    for index, srv in enumerate(SERVER_NAMES.values())
]


class AccountCog(commands.Cog):
    """Cog for managing whitelisted accounts on Project Zomboid servers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    account_group = app_commands.Group(
        name="account", description="Manage whitelisted accounts."
    )

    @account_group.command()
    @app_commands.choices(server=SERVER_CHOICES)
    @app_commands.describe(
        server="Which server?",
        username="Name for the new account.",
        password="Optional password. If omitted the player sets their own on join.",
    )
    @app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
    async def add(
        self,
        interaction: discord.Interaction,
        server: app_commands.Choice[int],
        username: str,
        password: Optional[str] = None,
    ):
        """Add a user to the whitelist."""
        username = username.strip()

        if has_invalid_quotes(username) or has_invalid_quotes(password or ""):
            await interaction.response.send_message(
                "Quotes are not allowed.", ephemeral=False
            )
            return

        await interaction.response.defer(ephemeral=False)

        system_user = SYSTEM_USERS[server.name]

        existing = await gamedb_get_player_by_name(system_user, username)
        if isinstance(existing, str):
            await interaction.followup.send(existing, ephemeral=False)
            return
        if existing:
            await interaction.followup.send(
                f"**{username}** is already whitelisted on the **{server.name}** server.",
                ephemeral=False,
            )
            return

        if not await server_isrunning(system_user):
            await interaction.followup.send(
                f"**{server.name}** is **NOT** running!", ephemeral=False
            )
            return

        success, response = await pz_add_user(system_user, username, password)
        if not success:
            await interaction.followup.send(response, ephemeral=False)
            return

        if password:
            msg = (
                f"Account **{username}** has been added to the **{server.name}** "
                f"whitelist with password: {password}"
            )
        else:
            msg = (
                f"Account **{username}** has been added to the **{server.name}** "
                f"whitelist without a password. "
                f"They will set their own password when they join."
            )

        await interaction.followup.send(msg, ephemeral=False)

    @account_group.command()
    @app_commands.choices(server=SERVER_CHOICES)
    @app_commands.describe(
        server="Which server?",
        username="Name of the account to remove.",
    )
    @app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
    async def remove(
        self,
        interaction: discord.Interaction,
        server: app_commands.Choice[int],
        username: str,
    ):
        """Remove a user from the whitelist."""
        username = username.strip()

        if has_invalid_quotes(username):
            await interaction.response.send_message(
                "Quotes are not allowed.", ephemeral=False
            )
            return

        await interaction.response.defer(ephemeral=False)

        system_user = SYSTEM_USERS[server.name]

        player_row = await gamedb_get_player_by_name(system_user, username)
        if isinstance(player_row, str):
            await interaction.followup.send(player_row, ephemeral=False)
            return
        if not player_row:
            await interaction.followup.send(
                f"**{username}** not found on the **{server.name}** server.",
                ephemeral=False,
            )
            return

        if not await server_isrunning(system_user):
            await interaction.followup.send(
                f"**{server.name}** is **NOT** running!", ephemeral=False
            )
            return

        success, response = await pz_remove_user(system_user, username)
        if not success:
            await interaction.followup.send(response, ephemeral=False)
            return

        await interaction.followup.send(
            f"Account **{username}** has been removed from the **{server.name}** "
            f"whitelist.",
            ephemeral=False,
        )

    @account_group.command(name="password_reset")
    @app_commands.choices(server=SERVER_CHOICES)
    @app_commands.describe(server="Which server?", playername="Which player?")
    @app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
    async def password_reset(
        self,
        interaction: discord.Interaction,
        server: app_commands.Choice[int],
        playername: str,
    ):
        """Reset a player's password to a new generated one."""
        playername = playername.strip()

        if has_invalid_quotes(playername):
            await interaction.response.send_message(
                "Quotes are not allowed.", ephemeral=False
            )
            return

        await interaction.response.defer(ephemeral=False)

        system_user = SYSTEM_USERS[server.name]
        game_version = get_game_version(system_user)

        if game_version == "UNKNOWN":
            await interaction.followup.send(
                f"Unable to determine game version for **{server.name}** server.",
                ephemeral=False,
            )
            return

        player_row = await gamedb_get_player_by_name(system_user, playername)
        if isinstance(player_row, str):
            await interaction.followup.send(player_row, ephemeral=False)
            return
        if not player_row:
            await interaction.followup.send(
                f"**{playername}** not found on the **{server.name}** server.",
                ephemeral=False,
            )
            return

        if not await server_isrunning(system_user):
            await interaction.followup.send(
                f"**{server.name}** is **NOT** running!", ephemeral=False
            )
            return

        new_pass = generate_pz_password(12)
        if game_version == "B42":
            success, response = await pz_setpassword_b42(
                system_user, playername, new_pass
            )
        else:
            success, response = await pz_reset_password_b41(
                system_user, playername, new_pass
            )

        if success:
            await interaction.followup.send(
                f"The password for {playername} has been reset to: {new_pass}",
                ephemeral=False,
            )
        else:
            await interaction.followup.send(response, ephemeral=False)

    @account_group.command(name="list")
    @app_commands.describe(player="Player's name or 17-digit SteamID.")
    @app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
    async def list(self, interaction: discord.Interaction, player: str):
        """List all accounts whitelisted under a player's SteamID."""
        player_input = player.strip()

        if has_invalid_quotes(player_input):
            await interaction.response.send_message(
                "Quotes are not allowed.", ephemeral=False
            )
            return

        await interaction.response.defer(ephemeral=False)

        steam_id, resolved = await resolve_steam_id(player_input)
        if not resolved or not steam_id:
            await interaction.followup.send(
                f"No player found matching **{player_input}** on any server.",
                ephemeral=False,
            )
            return

        accounts_by_server, errors_by_server = await find_accounts_by_steamid(steam_id)

        if not accounts_by_server and not errors_by_server:
            await interaction.followup.send(
                f"No whitelisted accounts found for SteamID **{steam_id}** "
                f"on any server.",
                ephemeral=False,
            )
            return

        total_accounts = sum(len(names) for names in accounts_by_server.values())
        lines = [
            f"SteamID **{steam_id}** has **{total_accounts}** account(s) whitelisted:",
            f"[Steam Profile](http://steamcommunity.com/profiles/{steam_id})",
        ]
        for server_name, names in accounts_by_server.items():
            lines.append(f"- **{server_name}**: {', '.join(names)}")
        for server_name, error in errors_by_server.items():
            lines.append(f"- ⚠️ {server_name}: {error}")

        await interaction.followup.send("\n".join(lines), ephemeral=False)
