import logging

from discord.ext import commands

from src.services.item_cache import item_cache
from src.services.vehicle_cache import vehicle_cache

logger = logging.getLogger(__name__)


class GameCacheCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        logger.info("Scanning server files for items...")
        await item_cache.scan_all_servers()
        logger.info("Scanning server files for vehicles...")
        await vehicle_cache.scan_all_servers()
