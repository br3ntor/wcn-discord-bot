import os
import datetime
from discord.ext import commands, tasks

ANNOUNCE_CHANNEL = int(os.getenv("ANNOUNCE_CHANNEL"))

california = datetime.timezone(datetime.timedelta(hours=-8))

times = [
    datetime.time(hour=2, tzinfo=california),
    datetime.time(hour=14, tzinfo=california),
]


class TasksCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.my_ad.start()

    def cog_unload(self):
        self.my_task.cancel()

    @tasks.loop(time=times)
    async def my_ad(self):
        ad_msg = "Help us to reach our monthly goal!\n"
        goal_url = "https://ko-fi.com/westcoastnoobs/goal"
        await self.bot.get_channel(ANNOUNCE_CHANNEL).send(ad_msg + goal_url)
        print("My ad is running!")
