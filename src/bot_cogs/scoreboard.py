import datetime
import logging

import discord
from discord.ext import commands, tasks

from src.config import Config

logger = logging.getLogger(__name__)

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL

california = datetime.timezone(datetime.timedelta(hours=-8))

times = [
    datetime.time(hour=6, tzinfo=california),
    datetime.time(hour=18, tzinfo=california),
]


class ScoreboardCog(commands.Cog):
    """Cog for posting periodic scoreboard link messages to Discord."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_unload(self):
        self.send_scoreboard.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Starting scoreboard tasks...")
        self.send_scoreboard.start()

    @tasks.loop(time=times)
    async def send_scoreboard(self):
        """Sends the scoreboard URL message to Discord."""
        chan = self.bot.get_channel(ANNOUNCE_CHANNEL)
        if not chan:
            logger.warning("Unable to get discord channel.")
            return
        if not isinstance(chan, discord.TextChannel):
            logger.warning("Chan is not TextChannel?")
            return

        await chan.send("https://westcoastnoobs.com")