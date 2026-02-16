import datetime

import discord
from discord.ext import commands, tasks

from src.config import Config

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL

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
        print("Starting advertisement tasks...")
        self.send_advertisement.start()

    @tasks.loop(time=times)
    async def send_advertisement(self):
        """Sends the donation goal advertisement message to Discord."""
        ad_msg = "Help us reach our monthly goal!\n"

        # This shows our goal but in a picture and we cant access the data
        # So if we want to stop ad if goal is reached we can access the db
        # To write a condition for it, TODO
        goal_url = "https://ko-fi.com/westcoastnoobs/goal"
        # chan = self.bot.get_channel(ANNOUNCE_CHANNEL)
        chan = self.bot.get_channel(948548630439165956)

        if not chan:
            print("Unable to get discord channel.")
            return
        if not isinstance(chan, discord.TextChannel):
            print("Chan is not TextChannel?")
            return

        await chan.send(ad_msg + goal_url)
        print("My ad is running!")