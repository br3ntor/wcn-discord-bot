import datetime
import logging

import discord
from discord.ext import commands, tasks

from src.utils.helpers import (
    KOFI_GOAL_URL,
    get_monthly_donation_progress,
    show_donation_progress,
)

logger = logging.getLogger(__name__)

# TODO: switch to Config.ANNOUNCE_CHANNEL when moving off the test server
ANNOUNCE_CHANNEL_ID = 948548630439165956

california = datetime.timezone(datetime.timedelta(hours=-8))

times = [
    datetime.time(hour=6, tzinfo=california),
    datetime.time(hour=18, tzinfo=california),
]


class AdvertisementCog(commands.Cog):
    """Cog for posting periodic donation advertisements to Discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_unload(self):
        self.send_advertisement.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Starting advertisement tasks...")
        self.send_advertisement.start()

    @tasks.loop(time=times)
    async def send_advertisement(self):
        """Sends the donation goal advertisement message to Discord."""
        current_amount, goal_amount = await get_monthly_donation_progress()
        if current_amount >= goal_amount:
            logger.info(
                "Donation goal met (%.2f/%.2f), skipping advertisement.",
                current_amount,
                goal_amount,
            )
            return

        chan = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if not isinstance(chan, discord.TextChannel):
            logger.warning("Unable to get announce TextChannel for advertisement.")
            return

        await chan.send(
            "Help us reach our monthly goal!\n"
            f"{show_donation_progress(current_amount, goal_amount)}\n"
            f"{KOFI_GOAL_URL}"
        )
        logger.info("Donation advertisement posted.")
