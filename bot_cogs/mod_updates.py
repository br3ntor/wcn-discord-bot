import asyncio
import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from config import Config
from lib.discord_utils import auto_restart_server
from lib.pz_workshop_error_scan import extract_workshop_ids, write_ids_to_file
from lib.server_utils import (
    combine_servers_workshop_ids,
    restart_zomboid_server,
    servers_with_mod_update,
)
from lib.steam_utils import get_workshop_items

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
MY_GUILD = Config.MY_GUILD
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID


class ModUpdatesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.error_check_counter = 0  # Initialize counter for limited iterations

    async def cog_unload(self):
        self.check_mod_updates.cancel()
        self.check_workshop_errors.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print("Starting mod updates tasks...")
        self.check_mod_updates.start()

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

                        # Trigger workshop error scanning after mod update restarts
                        if not self.check_workshop_errors.is_running():
                            self.error_check_counter = 0
                            self.check_workshop_errors.start()
                            print("Started workshop error scanning task")
                        else:
                            print("Workshop error scanning already running")
                    except Exception as e:
                        print(f"An unexpected exception occurred: {e}")

    @tasks.loop(minutes=1)
    async def check_workshop_errors(self):
        """Scans Modded_B42MP server logs for workshop errors and restarts affected server."""
        if self.error_check_counter >= 5:
            self.check_workshop_errors.cancel()
            print("Workshop error scan completed (5 iterations)")
            return

        self.error_check_counter += 1
        print(f"Workshop error scan iteration {self.error_check_counter}/5")

        # Only check Modded_B42MP server
        server_name = "Modded_B42MP"

        # Check if the server exists in configuration
        if server_name not in Config.SYSTEM_USERS:
            print(
                f"Server {server_name} not found in configuration. Stopping workshop error scan."
            )
            self.check_workshop_errors.cancel()
            return

        system_user = Config.SYSTEM_USERS[server_name]
        log_path = f"/home/{system_user}/log/console/pzserver-console.log"
        output_path = "/home/modded_pzserver42/pz_scripts/workshop_id.txt"

        try:
            error_ids = await extract_workshop_ids(log_path)

            # Somewhere in this if block we can cancel the continued check
            # i.e. we can run self.check_workshop_errors.cancel() somewhere
            # instead of just waiting for all 5 checks to finish
            if error_ids:
                print(f"Found workshop errors on {server_name}: {error_ids}")

                # Write IDs to specified file
                await write_ids_to_file(error_ids, output_path)
                print(f"Workshop IDs written to {output_path}")

                # Get announcement channel for notification
                chan = self.bot.get_channel(ANNOUNCE_CHANNEL)
                # chan = self.bot.get_channel(725232682690150481)
                if chan and isinstance(chan, discord.TextChannel):
                    # f"IDs written to {output_path}\n"
                    await chan.send(
                        f"🚨 **Workshop errors detected on {server_name}!**\n"
                        f"Problematic workshop IDs: {', '.join(error_ids)}\n"
                        f"Performing immediate server restart to apply fix..."
                    )

                # Use immediate restart function
                restart_success = await restart_zomboid_server(system_user)

                if chan and isinstance(chan, discord.TextChannel):
                    if restart_success:
                        await chan.send(
                            f"✅ **{server_name}** restarted successfully and will be back up soon."
                        )
                    else:
                        await chan.send(f"❌ Failed to restart **{server_name}**!")
            else:
                print(f"No workshop errors found on {server_name}")

        except FileNotFoundError:
            print(
                f"Log file not found for {server_name}: {log_path}. Stopping workshop error scan."
            )
            self.check_workshop_errors.cancel()
            return
        except Exception as e:
            print(
                f"Error checking workshop errors for {server_name}: {e}. Stopping workshop error scan."
            )
            self.check_workshop_errors.cancel()
            return