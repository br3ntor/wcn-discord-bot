import logging

from discord.ext import commands, tasks

from src.services.gist_updater import update_all_modlist_gists, update_all_sandbox_gists

logger = logging.getLogger(__name__)


class GistUpdaterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_unload(self):
        self.update_modlists.cancel()
        self.update_sandbox.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Starting gist updater tasks...")
        self.update_modlists.start()
        self.update_sandbox.start()

    @tasks.loop(hours=1)
    async def update_modlists(self):
        """Update all mod list gists hourly."""
        logger.info("Updating mod list gists...")
        try:
            links = await update_all_modlist_gists()
            logger.info("Updated %d mod list gist(s)", len(links))
        except Exception as e:
            logger.error("Error updating mod list gists: %s", e)

    @tasks.loop(hours=1)
    async def update_sandbox(self):
        """Update all sandbox settings gists hourly."""
        logger.info("Updating sandbox settings gists...")
        try:
            links = await update_all_sandbox_gists()
            logger.info("Updated %d sandbox settings gist(s)", len(links))
        except Exception as e:
            logger.error("Error updating sandbox settings gists: %s", e)

    @update_modlists.before_loop
    async def before_update_modlists(self):
        await self.bot.wait_until_ready()

    @update_sandbox.before_loop
    async def before_update_sandbox(self):
        await self.bot.wait_until_ready()
