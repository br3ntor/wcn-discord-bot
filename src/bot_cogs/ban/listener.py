import asyncio
import logging
from datetime import datetime, timezone
from typing import cast

import discord
from discord.ext import commands, tasks

from src.config import Config
from src.services.game_db import gamedb_get_ban_by_steamid
from src.services.pocketbase import pb_client
from src.services.pz_server import pz_ban_player, pz_unban_player
from src.services.server import server_isrunning

logger = logging.getLogger(__name__)


class BanListenerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._sse_started = False

    async def cog_load(self):
        if Config.pocketbase_configured:
            logger.info("PocketBase configured, starting ban listener...")
            await self.start_sse_listener()
            self.initial_sync.start()
            self.check_expired_bans.start()
        else:
            logger.info("PocketBase not configured, skipping ban listener")

    async def cog_unload(self):
        if self._sse_started:
            await pb_client.unsubscribe()
        self.initial_sync.cancel()
        self.check_expired_bans.cancel()

    async def start_sse_listener(self):
        await pb_client.subscribe(self.handle_ban_event)
        self._sse_started = True
        logger.info("SSE listener started for bans collection")

    async def handle_ban_event(self, action: str, record: dict):
        steamid = record.get("steamid")
        is_active = record.get("is_active", True)
        name = record.get("name", "Unknown")
        reason = record.get("reason", "No reason provided")
        server_origin = record.get("server_origin", "Unknown")
        expires = record.get("expires")

        if not steamid:
            logger.warning(f"Ban event with no steamid: {record}")
            return

        is_backfilled = "backfilled" in reason.lower()
        if is_backfilled:
            logger.info(f"Skipping backfilled ban event for {steamid}")
            return

        logger.info(
            f"Ban event: action={action}, steamid={steamid}, is_active={is_active}"
        )

        mod_chan = self.bot.get_channel(Config.MOD_CHANNEL)

        for system_user in Config.SYSTEM_USERS.values():
            if not await server_isrunning(system_user):
                logger.info(f"Skipping {system_user} - server not running")
                continue

            if action == "create" or (action == "update" and is_active):
                success, msg = await pz_ban_player(system_user, steamid)
                if success:
                    logger.info(f"Banned {steamid} on {system_user}")
                    if isinstance(mod_chan, discord.TextChannel):
                        server_name = Config.SERVER_NAMES.get(system_user, system_user)
                        embed = discord.Embed(
                            title=f"🚫 [{server_name}] Ban Issued",
                            color=discord.Color.red(),
                        )
                        embed.add_field(name="Player", value=name, inline=True)
                        embed.add_field(name="SteamID", value=steamid, inline=True)
                        embed.add_field(name="Reason", value=reason, inline=False)
                        embed.add_field(
                            name="Server Origin", value=server_origin, inline=True
                        )
                        if expires:
                            embed.add_field(name="Expires", value=expires, inline=True)
                        await mod_chan.send(embed=embed)
                else:
                    logger.warning(f"Failed to ban {steamid} on {system_user}: {msg}")

            elif action == "update" and not is_active:
                success, msg = await pz_unban_player(system_user, steamid)
                if success:
                    logger.info(f"Unbanned {steamid} on {system_user}")
                    if isinstance(mod_chan, discord.TextChannel):
                        server_name = Config.SERVER_NAMES.get(system_user, system_user)
                        embed = discord.Embed(
                            title=f"✅ [{server_name}] Ban Removed",
                            color=discord.Color.green(),
                        )
                        embed.add_field(name="Player", value=name, inline=True)
                        embed.add_field(name="SteamID", value=steamid, inline=True)
                        embed.add_field(
                            name="Server Origin", value=server_origin, inline=True
                        )
                        await mod_chan.send(embed=embed)
                else:
                    logger.warning(f"Failed to unban {steamid} on {system_user}: {msg}")

    @tasks.loop(count=1)
    async def initial_sync(self):
        await asyncio.sleep(1)

        if not Config.pocketbase_configured:
            return

        logger.info("Running initial ban sync from PocketBase...")

        bans = await pb_client.get_bans(is_active=True)
        if not bans:
            logger.info("No active bans in PocketBase")
            return

        unique_steamids = {
            steamid for ban in bans if (steamid := ban.get("steamid")) is not None
        }

        synced = 0
        already_present = 0
        db_lookup_failed = 0
        offline_servers = set()
        for steamid in unique_steamids:

            for system_user in Config.SYSTEM_USERS.values():
                if not await server_isrunning(system_user):
                    offline_servers.add(system_user)
                    continue

                existing_ban = await gamedb_get_ban_by_steamid(system_user, steamid)
                if isinstance(existing_ban, str):
                    db_lookup_failed += 1
                    logger.warning(
                        f"Skipping initial ban sync for {steamid} on {system_user}: {existing_ban}"
                    )
                    continue

                if existing_ban:
                    already_present += 1
                    continue

                success, _ = await pz_ban_player(system_user, steamid)
                if success:
                    synced += 1

        logger.info(
            "Initial sync complete: %s bans applied, %s already present, %s db lookups failed, %s offline servers",
            synced,
            already_present,
            db_lookup_failed,
            len(offline_servers),
        )

    @tasks.loop(hours=1)
    async def check_expired_bans(self):
        """Check for expired temporary bans and deactivate them."""
        logger.info("Checking for expired bans...")

        bans = await pb_client.get_bans(is_active=True)
        if not bans:
            logger.info("No active bans to check")
            return

        now = datetime.now(timezone.utc)
        expired_count = 0

        for ban in bans:
            expires = ban.get("expires")
            if not expires:
                continue

            try:
                expires_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                if expires_dt <= now:
                    ban_id = ban.get("id")
                    steamid = ban.get("steamid", "Unknown")
                    if ban_id:
                        success = await pb_client.deactivate_ban(ban_id)
                        if success:
                            expired_count += 1
                            logger.info(f"Deactivated expired ban for {steamid}")
                        else:
                            logger.warning(f"Failed to deactivate expired ban for {steamid}")
            except (ValueError, AttributeError) as e:
                logger.warning(f"Error parsing expires for ban {ban.get('id')}: {e}")

        if expired_count > 0:
            logger.info(f"Deactivated {expired_count} expired ban(s)")

    @check_expired_bans.before_loop
    async def before_check_expired_bans(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=30)
    async def retry_sse(self):
        if not self._sse_started and Config.pocketbase_configured:
            logger.info("Retrying SSE connection...")
            await self.start_sse_listener()
            if self._sse_started:
                cast(tasks.Loop, self.retry_sse).cancel()
