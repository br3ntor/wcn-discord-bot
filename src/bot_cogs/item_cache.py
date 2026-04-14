import logging

from discord.ext import commands

from src.services.item_cache import item_cache

logger = logging.getLogger(__name__)


class ItemCacheCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        logger.info("Scanning server files for items...")
        await item_cache.scan_all_servers()
