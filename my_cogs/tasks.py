import datetime

from discord.ext import commands, tasks

from config import Config
from utils.server_helpers import combine_servers_workshop_ids, servers_with_mod_update
from utils.steam_utils import get_workshop_items

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
MY_GUILD = Config.MY_GUILD
ADMIN_ROLE_ID = Config.ADMIN_ROLE_ID

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

        workshop_ids = await combine_servers_workshop_ids()
        workshop_items = await get_workshop_items(workshop_ids)

        for item in workshop_items:
            if "title" in item:
                now = datetime.datetime.now()
                time_updated = datetime.datetime.fromtimestamp(item["time_updated"])
                if (now - time_updated).total_seconds() / 60 < 5:

                    # Here we need to check on which servers the item exists
                    # Then we can use that in the output below
                    servers_with_mod = await servers_with_mod_update(
                        item["publishedfileid"]
                    )
                    print(servers_with_mod)

                    formatted_time = time_updated.strftime("%b %d @ %I:%M%p")
                    guild = self.bot.get_guild(MY_GUILD)
                    admin_role = guild.get_role(ADMIN_ROLE_ID).mention
                    update_msg = (
                        f"{admin_role} A mod has updated on **{'** and **'.join(servers_with_mod)}**!\n"
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
