import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from src.config import Config
from src.services.game_db import (
    gamedb_get_all_bans,
    gamedb_get_ban_by_steamid,
    gamedb_get_player_by_steamid,
)
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
            self.startup_sync.start()
            self.check_expired_bans.start()
        else:
            logger.info("PocketBase not configured, skipping ban listener")

    async def cog_unload(self):
        if self._sse_started:
            await pb_client.unsubscribe()
        self.startup_sync.cancel()
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

        logger.info(
            f"Ban event: action={action}, steamid={steamid}, is_active={is_active}"
        )

        mod_chan = self.bot.get_channel(Config.MOD_CHANNEL)

        for system_user in Config.SYSTEM_USERS.values():
            if not await server_isrunning(system_user):
                logger.debug(f"Skipping {system_user} - server not running")
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
                        await mod_chan.send(
                            f"✅ [{server_name}] Unbanned: {name} ({steamid})"
                        )
                else:
                    logger.warning(f"Failed to unban {steamid} on {system_user}: {msg}")

    @tasks.loop(count=1)
    async def startup_sync(self):
        """Full bidirectional sync between PocketBase and local servers.

        Runs before SSE subscription so no Discord messages are triggered.
        Steps:
        1. Sync unbans:  deactivate bans in PB → unban on servers
        2. Sync bans:    active bans in PB → ban on servers
        3. Backfill:     local server bans → create new PB records (no reactivation)
        """
        await asyncio.sleep(1)

        if not Config.pocketbase_configured:
            return

        if not await pb_client.login():
            logger.error("PocketBase login failed, skipping startup sync")
            return

        logger.info("Running startup ban sync...")

        # Step 1: Sync unbans — handle bans deactivated while bot was offline
        await self._sync_unbans()

        # Step 2: Sync active bans from PocketBase to servers
        await self._sync_active_bans()

        # Step 3: Backfill local server bans into PocketBase (new records only)
        await self._backfill_local_bans()

        # Step 4: Subscribe to SSE for real-time events
        logger.info("Startup sync complete, subscribing to SSE...")
        await self.start_sse_listener()

    async def _sync_unbans(self):
        """Fetch inactive bans from PB and unban on servers."""
        logger.info("Step 1/3: Syncing unbans from PocketBase...")

        inactive_bans = await pb_client.get_bans(is_active=False)
        if not inactive_bans:
            logger.debug("No inactive bans to sync")
            return

        unbanned = 0
        for ban in inactive_bans:
            steamid = ban.get("steamid")
            if not steamid:
                continue
            for system_user in Config.SYSTEM_USERS.values():
                if not await server_isrunning(system_user):
                    continue

                existing_ban = await gamedb_get_ban_by_steamid(system_user, steamid)
                if isinstance(existing_ban, str):
                    logger.warning(
                        f"Skipping unban sync for {steamid} on {system_user}: {existing_ban}"
                    )
                    continue

                if not existing_ban:
                    continue

                success, _ = await pz_unban_player(system_user, steamid)
                if success:
                    unbanned += 1

        logger.info("Step 1/3 complete: unbanned %d player(s)", unbanned)

    async def _sync_active_bans(self):
        """Fetch active bans from PB and apply to servers."""
        logger.info("Step 2/3: Syncing active bans from PocketBase...")

        bans = await pb_client.get_bans(is_active=True)
        if not bans:
            logger.debug("No active bans in PocketBase")
            return

        synced = 0
        already_present = 0
        db_lookup_failed = 0
        offline_servers = set()

        for ban in bans:
            steamid = ban.get("steamid")
            if not steamid:
                continue
            for system_user in Config.SYSTEM_USERS.values():
                if not await server_isrunning(system_user):
                    offline_servers.add(system_user)
                    continue

                existing_ban = await gamedb_get_ban_by_steamid(system_user, steamid)
                if isinstance(existing_ban, str):
                    db_lookup_failed += 1
                    logger.warning(
                        f"Skipping ban sync for {steamid} on {system_user}: {existing_ban}"
                    )
                    continue

                if existing_ban:
                    already_present += 1
                    continue

                success, _ = await pz_ban_player(system_user, steamid)
                if success:
                    synced += 1

        logger.info(
            "Step 2/3 complete: %d bans applied, %d already present, %d db lookups failed, %d offline servers",
            synced,
            already_present,
            db_lookup_failed,
            len(offline_servers),
        )

    async def _backfill_local_bans(self):
        """Read local server bans and create new PB records (no reactivation)."""
        logger.info("Step 3/3: Backfilling local server bans to PocketBase...")

        # Collect all bans from local server DBs
        local_bans: dict[str, dict] = {}
        scanned_rows = 0
        failed_servers = []

        for server_name, system_user in Config.SYSTEM_USERS.items():
            server_bans = await gamedb_get_all_bans(system_user)

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

                player_row = await gamedb_get_player_by_steamid(system_user, steamid)
                if isinstance(player_row, str) or not player_row:
                    player_name = "Unknown"
                else:
                    player_name = player_row[2] or "Unknown"

                local_bans[steamid] = {
                    "name": player_name,
                    "server_origin": server_name,
                }

        # Bulk fetch all PB bans to check which local bans already exist
        pb_bans = await pb_client.get_bans()
        pb_existing_steamids = {
            ban.get("steamid") for ban in pb_bans if ban.get("steamid")
        }
        pb_bans_by_steamid = {
            ban.get("steamid"): ban for ban in pb_bans if ban.get("steamid")
        }
        reactivation_candidates = [
            sid
            for sid in local_bans
            if sid in pb_existing_steamids
            and not pb_bans_by_steamid.get(sid, {}).get("is_active", False)
        ]

        # Only create records for steamids not in PocketBase at all
        to_create = {
            sid: data
            for sid, data in local_bans.items()
            if sid not in pb_existing_steamids
        }

        created_count = 0
        failed_steamids = []

        for steamid, local_ban in to_create.items():
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

        if reactivation_candidates:
            logger.warning(
                "Skipped reactivation of %d inactive ban(s) (exist in PB but banned locally): %s",
                len(reactivation_candidates),
                ", ".join(reactivation_candidates[:10]),
            )

        logger.info(
            "Step 3/3 complete: scanned %d rows across %d server(s), found %d unique steamids, "
            "created %d new PB records, %d already in PB, %d skipped reactivation",
            scanned_rows,
            len(Config.SYSTEM_USERS) - len(failed_servers),
            len(local_bans),
            created_count,
            len(pb_existing_steamids),
            len(reactivation_candidates),
        )

        if failed_servers:
            logger.warning("Failed to read from servers: %s", ", ".join(failed_servers))
        if failed_steamids:
            logger.warning(
                "Failed to create PB records for: %s",
                ", ".join(failed_steamids[:10]),
            )

    @tasks.loop(hours=1)
    async def check_expired_bans(self):
        """Check for expired temporary bans and deactivate them."""
        logger.debug("Checking for expired bans...")

        bans = await pb_client.get_bans(is_active=True)
        if not bans:
            logger.debug("No active bans to check")
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
                            logger.warning(
                                f"Failed to deactivate expired ban for {steamid}"
                            )
            except (ValueError, AttributeError) as e:
                logger.warning(f"Error parsing expires for ban {ban.get('id')}: {e}")

        if expired_count > 0:
            logger.info(f"Deactivated {expired_count} expired ban(s)")

    @check_expired_bans.before_loop
    async def before_check_expired_bans(self):
        await self.bot.wait_until_ready()
