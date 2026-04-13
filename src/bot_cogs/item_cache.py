import logging

from discord.ext import commands

from src.services.item_cache import item_cache

logger = logging.getLogger(__name__)


class ItemCacheCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        loaded = item_cache.load_from_disk()
        if not loaded:
            logger.info("No item cache found, scanning server files...")
            await item_cache.scan_all_servers()
        else:
            logger.info("Item cache loaded from disk")
