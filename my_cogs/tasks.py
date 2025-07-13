import asyncio
import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from config import Config
from lib.discord_utils import auto_restart_server
from lib.server_utils import combine_servers_workshop_ids, servers_with_mod_update
from lib.steam_utils import get_workshop_items

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
MY_GUILD = Config.MY_GUILD
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID

california = datetime.timezone(datetime.timedelta(hours=-8))

times = [
    datetime.time(hour=6, tzinfo=california),
    datetime.time(hour=18, tzinfo=california),
]


class TasksCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_unload(self):
        self.check_mod_updates.cancel()
        self.my_ad.cancel()
        self.scoreboard_message.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print("Starting tasks...")
        self.check_mod_updates.start()
        self.my_ad.start()
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

    @tasks.loop(time=times)
    async def my_ad(self):
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

    @tasks.loop(minutes=5)
    async def check_mod_updates(self):
        """Checks if mod has been updated in the last n minutes.
        Sends ping to admins if there is updates"""
        print("Checking for mod updates...")

        workshop_ids = await combine_servers_workshop_ids()
        workshop_items = await get_workshop_items(workshop_ids)

        for item in workshop_items:
            if "title" in item:

                local_time = ZoneInfo("localtime")
                now = datetime.datetime.now(local_time)

                # Convert the timestamp to a timezone-aware datetime object
                time_updated = datetime.datetime.fromtimestamp(
                    item["time_updated"], tz=local_time
                )

                # TODO: Maybe trigger auto restart code here
                if (now - time_updated).total_seconds() / 60 < 5:

                    # Here we need to check on which servers the item exists
                    # Then we can use that in the output below
                    servers_with_mod = await servers_with_mod_update(
                        item["publishedfileid"]
                    )
                    print(servers_with_mod)

                    formatted_time = time_updated.strftime("%b %d @ %I:%M%p %Z")

                    guild = self.bot.get_guild(MY_GUILD)
                    if not guild:
                        print("Unable to get guild")
                        return
                    ar = guild.get_role(PZ_ADMIN_ROLE_ID)
                    if not ar:
                        print("Unable to get admin role id")
                        return
                    admin_role = ar.mention

                    update_msg = (
                        f"{admin_role} A mod has updated on **{'** and **'.join(servers_with_mod)}**!\n"
                        f"Title: {item['title'].strip()}\n"
                        f"Updated: {formatted_time}\n"
                        f"https://steamcommunity.com/sharedfiles/filedetails/?id={item['publishedfileid']}"
                    )

                    chan = self.bot.get_channel(ANNOUNCE_CHANNEL)
                    if not chan:
                        print("Unable to get discord channel.")
                        return
                    if not isinstance(chan, discord.TextChannel):
                        print("Chan is not TextChannel?")
                        return

                    await chan.send(update_msg)

                    print("A mod has updated!")
                    print(f"title: {item['title'].strip()}")
                    print(f"updated: {formatted_time}")
                    print(
                        f"https://steamcommunity.com/sharedfiles/filedetails/?id={item['publishedfileid']}"
                    )

                    # Run auto restart for each server containing updated mod concurrently
                    tasks = [
                        auto_restart_server(
                            chan,
                            server_name,
                            f"Auto restart triggered for the **{server_name}** server. Restarting in 5min.",
                        )
                        for server_name in servers_with_mod
                    ]
                    try:
                        results = await asyncio.gather(*tasks)
                        print("Results:", results)
                    except Exception as e:
                        print(f"An unexpected exception occurred: {e}")
