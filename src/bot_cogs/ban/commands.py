"""Ban management cog for Discord bot."""

import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from tabulate import tabulate

from src.config import Config
from src.services.game_db import get_all_banned_players, get_player_by_steamid
from src.services.pocketbase import pb_client
from src.services.pz_server import pz_ban_player, pz_unban_player
from src.services.server import server_isrunning

from .utils import has_invalid_quotes, lookup_player, resolve_steam_id
from .views import BanListView

logger = logging.getLogger(__name__)

SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID
SERVER_CHOICES: list[app_commands.Choice[int]] = [
    app_commands.Choice(name=srv, value=index + 1)
    for index, srv in enumerate(SERVER_NAMES.values())
]


class BanCommandsCog(commands.Cog):
    """Cog for managing player bans across Project Zomboid servers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _should_use_pocketbase(self) -> bool:
        """Check if PocketBase should be used for ban operations."""
        listener_enabled = Config.COGS_CONFIG.get("ban.listener", {}).get(
            "enabled", False
        )
        return Config.pocketbase_configured and listener_enabled

    ban_group = app_commands.Group(
        name="ban", description="Ban, unban, and list banned players."
    )

    @ban_group.command()
    @app_commands.choices(server=SERVER_CHOICES)
    @app_commands.describe(
        server="Which server?",
        player="Enter player's name or SteamID.",
        reason="Reason for the ban (optional).",
        days="Number of days for the ban (optional, permanent if not specified).",
    )
    @app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
    async def issue(
        self,
        interaction: discord.Interaction,
        server: app_commands.Choice[int],
        player: str,
        reason: Optional[str] = None,
        days: Optional[int] = None,
    ):
        """Ban a player by name or SteamID."""
        player_input = player.strip()
        await interaction.response.defer()

        system_user = SYSTEM_USERS[server.name]
        steam_id, player_name, error = await lookup_player(system_user, player_input)

        if error:
            await interaction.followup.send(error)
            return

        assert steam_id is not None

        if not await server_isrunning(system_user):
            await interaction.followup.send(f"**{server.name}** is **NOT** running!")
            return

        # Calculate expiration if days provided
        expires = None
        if days is not None and days > 0:
            expires = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

        pb_result = None
        ban_status = "banned"
        use_pocketbase = self._should_use_pocketbase()
        ban_reason = reason if reason else "Banned via Discord command"

        if use_pocketbase:
            existing_ban = await pb_client.get_ban_by_steamid(steam_id)
            if existing_ban:
                ban_id = existing_ban.get("id")
                if ban_id:
                    was_active = existing_ban.get("is_active", False)
                    pb_result = await pb_client.update_ban(
                        ban_id,
                        {
                            "is_active": True,
                            "name": player_name or "Unknown",
                            "reason": ban_reason,
                            "server_origin": server.name,
                            "expires": expires,
                        },
                    )
                    if pb_result:
                        ban_status = "already banned" if was_active else "banned"
            else:
                pb_result = await pb_client.create_ban(
                    steamid=steam_id,
                    name=player_name or "Unknown",
                    reason=ban_reason,
                    server_origin=server.name,
                    expires=expires,
                )

        if not pb_result:
            success, response = await pz_ban_player(system_user, steam_id)
            if success:
                if not use_pocketbase:
                    fallback_reason = (
                        "PocketBase not configured"
                        if not Config.pocketbase_configured
                        else "Ban listener disabled"
                    )
                else:
                    fallback_reason = "PocketBase unavailable"

                expires_info = (
                    f"⏰ Expires: {expires if expires else 'Permanent'}\n"
                    if expires
                    else ""
                )
                msg = (
                    f"Player has been **banned** from the **{server.name}** server.\n"
                    f"Username: **{player_name or '(unknown)'}**\n"
                    f"SteamID: **{steam_id}**\n"
                    f"{expires_info}⚠️ Banned locally - {fallback_reason}"
                )
            else:
                msg = f"Ban failed for SteamID **{steam_id}**: {response}"
        else:
            expires_info = (
                f"⏰ Expires: {expires if expires else 'Permanent'}\n"
                if expires
                else ""
            )
            msg = (
                f"Player has been **{ban_status}**.\n"
                f"Username: **{player_name or '(unknown)'}**\n"
                f"SteamID: **{steam_id}**\n"
                f"{expires_info}✅ Synced to PocketBase - ban will be applied to all servers"
            )

        await interaction.followup.send(msg)

    @ban_group.command()
    @app_commands.choices(server=SERVER_CHOICES)
    @app_commands.describe(
        server="Which server?",
        player="Enter player's name or SteamID.",
    )
    @app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
    async def revoke(
        self,
        interaction: discord.Interaction,
        server: app_commands.Choice[int],
        player: str,
    ):
        """Unban a player by name or SteamID."""
        player_input = player.strip()
        await interaction.response.defer()

        system_user = SYSTEM_USERS[server.name]
        steam_id, player_name, error = await lookup_player(system_user, player_input)

        if error:
            await interaction.followup.send(error)
            return

        assert steam_id is not None

        pb_unbanned = False
        use_pocketbase = self._should_use_pocketbase()

        if use_pocketbase:
            bans = await pb_client.get_bans(is_active=True)
            for ban in bans:
                if ban.get("steamid") == steam_id:
                    ban_id = ban.get("id")
                    if ban_id:
                        pb_unbanned = await pb_client.deactivate_ban(ban_id)
                    break

        if not pb_unbanned:
            success, response = await pz_unban_player(system_user, steam_id)
            if success:
                if not use_pocketbase:
                    fallback_reason = (
                        "PocketBase not configured"
                        if not Config.pocketbase_configured
                        else "Ban listener disabled"
                    )
                else:
                    fallback_reason = "PocketBase unavailable"

                msg = (
                    f"Player has been **unbanned** from the **{server.name}** server.\n"
                    f"Username: **{player_name or '(unknown)'}**\n"
                    f"SteamID: **{steam_id}**\n"
                    f"⚠️ Unbanned locally - {fallback_reason}"
                )
            else:
                msg = f"Unban failed for SteamID **{steam_id}**: {response}"
        else:
            msg = (
                f"Player has been **unbanned**.\n"
                f"Username: **{player_name or '(unknown)'}**\n"
                f"SteamID: **{steam_id}**\n"
                f"✅ Synced to PocketBase - unban will be applied to all servers"
            )

        await interaction.followup.send(msg)

    @ban_group.command()
    @app_commands.describe(
        player="Enter player's name or SteamID.",
    )
    @app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
    async def check(self, interaction: discord.Interaction, player: str):
        """Check if a player is banned."""
        player_input = player.strip()
        
        if has_invalid_quotes(player_input):
            await interaction.response.send_message("Quotes are not allowed.")
            return
        
        await interaction.response.defer()

        use_pocketbase = self._should_use_pocketbase()
        pb_bans = []
        steam_id = ""
        is_steamid = player_input.isdigit() and len(player_input) == 17

        if use_pocketbase:
            if is_steamid:
                steam_id = player_input
                ban = await pb_client.get_ban_by_steamid(steam_id)
                if ban:
                    pb_bans = [ban]
            else:
                pb_bans = await pb_client.get_bans_by_name(player_input)
                if not pb_bans:
                    steam_id, resolved = await resolve_steam_id(player_input)
                    if resolved and steam_id:
                        ban = await pb_client.get_ban_by_steamid(steam_id)
                        if ban:
                            pb_bans.append(ban)
                    if not steam_id:
                        steam_id = player_input
        else:
            if is_steamid:
                steam_id = player_input
            else:
                steam_id, resolved = await resolve_steam_id(player_input)
                if not steam_id:
                    steam_id = player_input

            local_bans = []
            for system_user in SYSTEM_USERS.values():
                bans = await get_all_banned_players(system_user)
                if isinstance(bans, str):
                    continue
                for ban_row in bans:
                    if ban_row[0] == steam_id:
                        local_bans.append(
                            {
                                "steamid": ban_row[0],
                                "name": player_input if not is_steamid else "Unknown",
                                "is_active": True,
                            }
                        )
            pb_bans = local_bans

        if pb_bans:
            embed = discord.Embed(
                title="🛡️ Ban Record Found",
                color=discord.Color.red(),
            )

            for ban in pb_bans:
                is_active = ban.get("is_active", False)
                status_emoji = "🔴" if is_active else "⚪"
                status = (
                    f"{status_emoji} Active"
                    if is_active
                    else f"{status_emoji} Inactive"
                )
                reason = ban.get("reason", "No reason")
                server_origin = ban.get("server_origin", "N/A")
                expires = ban.get("expires")
                ban_name = ban.get("name", "Unknown")
                ban_steamid = ban.get("steamid", "Unknown")

                if expires:
                    try:
                        expires_dt = datetime.fromisoformat(
                            expires.replace("Z", "+00:00")
                        )
                        now = datetime.now(timezone.utc)
                        time_diff = expires_dt - now

                        expires_formatted = expires_dt.strftime(
                            "%Y-%m-%d at %I:%M %p UTC"
                        )

                        if time_diff.total_seconds() > 0:
                            total_seconds = int(time_diff.total_seconds())
                            days = total_seconds // 86400
                            hours = (total_seconds % 86400) // 3600
                            if days > 0:
                                time_remaining = f"{days} day{'s' if days != 1 else ''}, {hours} hour{'s' if hours != 1 else ''}"
                            else:
                                time_remaining = (
                                    f"{hours} hour{'s' if hours != 1 else ''}"
                                )
                            expires_display = f"{time_remaining}\n({expires_formatted})"
                        else:
                            expires_display = f"Expired\n({expires_formatted})"
                    except (ValueError, AttributeError):
                        expires_display = expires
                else:
                    expires_display = "Permanent"

                field_value = (
                    f"Target: {ban_name}\n"
                    f"SteamID: {ban_steamid}\n"
                    f"\n"
                    f"Current Status: {status}\n"
                    f"Reason: {reason}\n"
                    f"Server: {server_origin}\n"
                    f"\n"
                    f"Expires In: {expires_display}"
                )

                embed.add_field(
                    name="",
                    value=field_value,
                    inline=False,
                )

            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(
                title="🛡️ No Ban Record",
                description=f"No ban found for **{player_input}**.",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed)

    @ban_group.command()
    @app_commands.choices(server=SERVER_CHOICES)
    @app_commands.describe(
        server="Which server?",
    )
    @app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
    async def list(
        self, interaction: discord.Interaction, server: app_commands.Choice[int]
    ):
        """Retrieve a list of all banned players on the selected server."""
        await interaction.response.defer()
        system_user = SYSTEM_USERS[server.name]

        servers_banned_players = await get_all_banned_players(system_user)

        if not servers_banned_players:
            await interaction.followup.send("No banned players on this server.")
            return

        banned_players = []
        seen_players = []
        for b_player in servers_banned_players:
            steamid = b_player[0]

            if steamid in seen_players:
                continue

            seen_players.append(steamid)

            user = await get_player_by_steamid(system_user, steamid)
            if not user:
                banned_players.append(("None", steamid))
                continue
            elif isinstance(user, str):
                continue

            banned_players.append((user[2], steamid))

        category = next(k for k, v in SYSTEM_USERS.items() if v == system_user)

        banned_list = [[p[0], p[1]] for p in banned_players]
        msg = f"{category} Bans:\n{tabulate(banned_list, headers=['Name', 'SteamID'])}"

        note = (
            "If the players name is None then they were banned before ever joining.\n\n"
        )

        if not msg:
            await interaction.followup.send("No banned players on this server.")
            return

        content = note + msg
        file = discord.File(
            io.BytesIO(content.encode()), filename=f"banned_{category}.txt"
        )
        await interaction.followup.send(f"Banned list for {category}:", file=file)

    @ban_group.command()
    @app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
    async def sync(self, interaction: discord.Interaction):
        """Force sync bans from PocketBase to all servers."""
        await interaction.response.defer()

        if not Config.pocketbase_configured:
            await interaction.followup.send("PocketBase is not configured.")
            return

        bans = await pb_client.get_bans(is_active=True)

        if not bans:
            await interaction.followup.send("No active bans in PocketBase.")
            return

        synced_count = 0
        failed_servers = []

        for ban in bans:
            steamid = ban.get("steamid")
            if not steamid:
                continue

            for system_user in SYSTEM_USERS.values():
                if await server_isrunning(system_user):
                    success, _ = await pz_ban_player(system_user, steamid)
                    if success:
                        synced_count += 1
                else:
                    if system_user not in failed_servers:
                        failed_servers.append(system_user)

        msg = f"Synced **{len(bans)}** bans from PocketBase."
        if failed_servers:
            msg += f"\n⚠️ Offline servers: {', '.join(failed_servers)}"

        await interaction.followup.send(msg)

    @ban_group.command()
    @app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
    async def backfill(self, interaction: discord.Interaction):
        """Backfill local server bans into PocketBase."""
        await interaction.response.defer()

        if not Config.pocketbase_configured:
            await interaction.followup.send("PocketBase is not configured.")
            return

        pb_bans = await pb_client.get_all_bans()
        pb_bans_by_steamid = {
            ban.get("steamid"): ban for ban in pb_bans if ban.get("steamid")
        }

        local_bans = {}
        scanned_rows = 0
        failed_servers = []

        for server_name, system_user in SYSTEM_USERS.items():
            server_bans = await get_all_banned_players(system_user)

            if isinstance(server_bans, str):
                failed_servers.append(server_name)
                logger.warning(
                    f"Skipping local ban backfill for {server_name}: {server_bans}"
                )
                continue

            for ban_row in server_bans:
                scanned_rows += 1
                steamid = ban_row[0]
                if not steamid or steamid in local_bans:
                    continue

                player_row = await get_player_by_steamid(system_user, steamid)
                if isinstance(player_row, str) or not player_row:
                    player_name = "Unknown"
                else:
                    player_name = player_row[2] or "Unknown"

                local_bans[steamid] = {
                    "name": player_name,
                    "server_origin": server_name,
                }

        created_count = 0
        reactivated_count = 0
        skipped_count = 0
        failed_steamids = []

        for steamid, local_ban in local_bans.items():
            existing_ban = pb_bans_by_steamid.get(steamid)

            if existing_ban:
                if existing_ban.get("is_active", False):
                    skipped_count += 1
                    continue

                ban_id = existing_ban.get("id")
                if not ban_id:
                    failed_steamids.append(steamid)
                    logger.warning(
                        f"Cannot reactivate PocketBase ban without id: {steamid}"
                    )
                    continue

                result = await pb_client.update_ban(
                    ban_id,
                    {
                        "is_active": True,
                        "name": local_ban["name"],
                        "reason": "Backfilled from local server ban list",
                        "server_origin": local_ban["server_origin"],
                    },
                )
                if result:
                    reactivated_count += 1
                else:
                    failed_steamids.append(steamid)
                continue

            result = await pb_client.create_ban(
                steamid=steamid,
                name=local_ban["name"],
                reason="Backfilled from local server ban list",
                server_origin=local_ban["server_origin"],
            )
            if result:
                created_count += 1
            else:
                failed_steamids.append(steamid)

        msg_lines = [
            "Local ban backfill complete.",
            f"Scanned **{len(SYSTEM_USERS)}** servers.",
            f"Found **{scanned_rows}** local ban rows.",
            f"Found **{len(local_bans)}** unique SteamIDs.",
            f"Created **{created_count}** PocketBase bans.",
            f"Reactivated **{reactivated_count}** PocketBase bans.",
            f"Skipped **{skipped_count}** already-active PocketBase bans.",
            f"Failed **{len(failed_steamids)}** PocketBase writes.",
        ]

        if failed_servers:
            msg_lines.append(f"Warnings: failed to read {', '.join(failed_servers)}")

        if failed_steamids:
            preview = ", ".join(failed_steamids[:10])
            suffix = "..." if len(failed_steamids) > 10 else ""
            msg_lines.append(f"Failed SteamIDs: {preview}{suffix}")

        await interaction.followup.send("\n".join(msg_lines))

    @ban_group.command()
    @app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
    async def list_global(self, interaction: discord.Interaction):
        """List all bans from PocketBase with pagination."""
        await interaction.response.defer()

        if not Config.pocketbase_configured:
            await interaction.followup.send("PocketBase is not configured.")
            return

        result = await pb_client.get_bans_paginated(page=1, per_page=50)
        bans = result.get("items", [])

        if not bans:
            await interaction.followup.send("No bans in PocketBase.")
            return

        view = BanListView(
            page=result.get("page", 1),
            total_pages=result.get("totalPages", 1),
            total_items=result.get("totalItems", 0),
        )

        await interaction.followup.send(embed=view.build_embed(bans), view=view)
