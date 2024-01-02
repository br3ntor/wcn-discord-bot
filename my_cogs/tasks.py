import os
import datetime
from discord.ext import commands, tasks
from utils.steam_utils import get_mod_ids, get_mod_data

ANNOUNCE_CHANNEL = int(os.getenv("ANNOUNCE_CHANNEL"))
SPAM_CHANNEL = int(os.getenv("SPAM_CHANNEL"))
MY_GUILD = int(os.getenv("MY_GUILD"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))

california = datetime.timezone(datetime.timedelta(hours=-8))

times = [
    datetime.time(hour=2, tzinfo=california),
    datetime.time(hour=14, tzinfo=california),
]


class TasksCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cog_unload(self):
        self.check_mod_updates.cancel()
        # self.my_ad.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print("Starting tasks...")
        self.check_mod_updates.start()
        # self.my_ad.start()

    @tasks.loop(time=times)
    async def my_ad(self):
        ad_msg = "Help us to reach our monthly goal!\n"
        goal_url = "https://ko-fi.com/westcoastnoobs/goal"
        await self.bot.get_channel(ANNOUNCE_CHANNEL).send(ad_msg + goal_url)
        print("My ad is running!")

    @tasks.loop(minutes=5)
    async def check_mod_updates(self):
        """Checks if mod has been updated in the last n minutes.
        Sends ping to admins if there is updates"""
        print("Checking for mod updates...")
        workshop_items = get_mod_data(get_mod_ids())
        for item in workshop_items["response"]["publishedfiledetails"]:
            if "title" in item:
                now = datetime.datetime.now()
                time_updated = datetime.datetime.fromtimestamp(item["time_updated"])
                if (now - time_updated).total_seconds() / 60 < 6:
                    formatted_time = time_updated.strftime("%b %d @ %I:%M%p")
                    guild = self.bot.get_guild(MY_GUILD)
                    admin_role = guild.get_role(ADMIN_ROLE_ID).mention
                    update_msg = (
                        f"{admin_role} A mod has updated!\n"
                        f"Title: {item['title'].strip()}\n"
                        f"Updated: {formatted_time}\n"
                        f"https://steamcommunity.com/sharedfiles/filedetails/?id={item['publishedfileid']}"
                    )
                    await self.bot.get_channel(ANNOUNCE_CHANNEL).send(update_msg)
                    print("A mod has updated!")
                    print(f"title: {item['title'].strip()}")
                    print(f"updated: {formatted_time}")
                    print(
                        f"https://steamcommunity.com/sharedfiles/filedetails/?id={item['publishedfileid']}"
                    )
