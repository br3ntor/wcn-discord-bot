import os
import datetime
from discord.ext import commands, tasks

SPAM_CHANNEL = int(os.getenv("SPAM_CHANNEL"))

california = datetime.timezone(datetime.timedelta(hours=-8))
time = datetime.time(hour=16, minute=13, tzinfo=california)

times = [
    datetime.time(hour=0, tzinfo=california),
    datetime.time(hour=4, tzinfo=california),
    datetime.time(hour=8, tzinfo=california),
    datetime.time(hour=12, tzinfo=california),
    datetime.time(hour=16, tzinfo=california),
    datetime.time(hour=20, tzinfo=california),
]


class TasksCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # self.my_task.start()
        # self.spammer.start()

    def cog_unload(self):
        self.my_task.cancel()
        self.spammer.cancel()

    @tasks.loop(time=time)
    async def my_task(self):
        print("My task is running!")

    @tasks.loop(seconds=5.0)
    async def spammer(self):
        test = self.bot.get_channel(SPAM_CHANNEL)
        if test:
            await test.send("spam")
        print(type(test))
        print(test)
        print("go go go")
