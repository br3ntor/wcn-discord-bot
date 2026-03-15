import asyncio
import logging

from discord.ext import commands, tasks

from src.config import Config
from src.services.pocketbase import pb_client
from src.services.pz_server import pz_ban_player, pz_unban_player
from src.services.server import server_isrunning

logger = logging.getLogger(__name__)


class BanListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._sse_started = False

    async def cog_load(self):
        if Config.pocketbase_configured:
            logger.info("PocketBase configured, starting ban listener...")
            await self.start_sse_listener()
            await self.initial_sync.start()
        else:
            logger.info("PocketBase not configured, skipping ban listener")

    async def cog_unload(self):
        if self._sse_started:
            await pb_client.unsubscribe()
        await self.initial_sync.cancel()

    async def start_sse_listener(self):
        await pb_client.subscribe(self.handle_ban_event)
        self._sse_started = True
        logger.info("SSE listener started for bans collection")

    async def handle_ban_event(self, action: str, record: dict):
        steamid = record.get("steamid")
        is_active = record.get("is_active", True)

        if not steamid:
            logger.warning(f"Ban event with no steamid: {record}")
            return

        logger.info(
            f"Ban event: action={action}, steamid={steamid}, is_active={is_active}"
        )

        for system_user in Config.SYSTEM_USERS.values():
            if not await server_isrunning(system_user):
                logger.info(f"Skipping {system_user} - server not running")
                continue

            if action == "create" or (action == "update" and is_active):
                success, msg = await pz_ban_player(system_user, steamid)
                if success:
                    logger.info(f"Banned {steamid} on {system_user}")
                else:
                    logger.warning(f"Failed to ban {steamid} on {system_user}: {msg}")

            elif action == "update" and not is_active:
                success, msg = await pz_unban_player(system_user, steamid)
                if success:
                    logger.info(f"Unbanned {steamid} on {system_user}")
                else:
                    logger.warning(f"Failed to unban {steamid} on {system_user}: {msg}")

    # A loop that runs 1 time and sleeps 1 second before any action hmmm...
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

        synced = 0
        for ban in bans:
            steamid = ban.get("steamid")
            if not steamid:
                continue

            for system_user in Config.SYSTEM_USERS.values():
                if not await server_isrunning(system_user):
                    continue

                success, _ = await pz_ban_player(system_user, steamid)
                if success:
                    synced += 1

        logger.info(f"Initial sync complete: {synced} bans applied")

    @tasks.loop(seconds=30)
    async def retry_sse(self):
        if not self._sse_started and Config.pocketbase_configured:
            logger.info("Retrying SSE connection...")
            await self.start_sse_listener()
            if self._sse_started:
                self.retry_sse.cancel()
