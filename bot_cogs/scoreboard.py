import datetime

import discord
from discord.ext import commands, tasks

from config import Config

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL

california = datetime.timezone(datetime.timedelta(hours=-8))

times = [
    datetime.time(hour=6, tzinfo=california),
    datetime.time(hour=18, tzinfo=california),
]


class ScoreboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_unload(self):
        self.scoreboard_message.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print("Starting scoreboard tasks...")
        self.scoreboard_message.start()

    @tasks.loop(time=times)
    async def scoreboard_message(self):
        chan = self.bot.get_channel(ANNOUNCE_CHANNEL)
        if not chan:
            print("Unable to get discord channel.")
            return
        if not isinstance(chan, discord.TextChannel):
            print("Chan is not TextChannel?")
            return

        await chan.send("https://westcoastnoobs.com")