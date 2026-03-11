import asyncio
import datetime
import logging
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from src.config import Config
from src.features.auto_restart import auto_restart
from src.services.server import (
    combine_servers_workshop_ids,
    get_servers_workshop_ids,
    restart_zomboid_server,
    server_setting_paths,
    servers_with_mod_update,
)
from src.services.steam import get_workshop_items
from src.services.workshop import extract_workshop_ids, write_ids_to_file

logger = logging.getLogger(__name__)

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
MY_GUILD = Config.MY_GUILD
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID


class ModUpdatesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.server_error_counters: dict[str, int] = {}
        self.mod_update_times: dict[str, int] = {}
        self.workshop_ids: list[str] | None = None

    async def cog_unload(self):
        self.check_mod_updates.cancel()
        self.check_workshop_errors.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Starting mod updates tasks...")
        self.check_mod_updates.start()

    @tasks.loop(minutes=5)
    async def check_mod_updates(self):
        """Checks if mods have been updated since last check.
        Sends ping to admins if there are updates."""
        logger.info("Checking for mod updates...")

        # Dynamically fetch the latest workshop IDs from running servers
        current_workshop_ids = await combine_servers_workshop_ids()

        if not current_workshop_ids:
            logger.info("No workshop IDs found on any running servers, skipping check")
            return

        self.workshop_ids = current_workshop_ids
        workshop_items = await get_workshop_items(self.workshop_ids)

        for item in workshop_items:
            if "title" not in item:
                continue

            workshop_id = item["publishedfileid"]

            # If we've never seen this mod before (newly added to config)
            if workshop_id not in self.mod_update_times:
                logger.info(
                    f"Discovered new mod: {item['title'].strip()} ({workshop_id}). Recording initial timestamp."
                )
                self.mod_update_times[workshop_id] = item["time_updated"]
                continue

            stored_time = self.mod_update_times[workshop_id]

            if item["time_updated"] > stored_time:
                self.mod_update_times[workshop_id] = item["time_updated"]

                servers_with_mod = await servers_with_mod_update(
                    item["publishedfileid"]
                )

                if not servers_with_mod:
                    logger.info(
                        f"Mod {workshop_id} updated, but no running servers are using it. Skipping announcement."
                    )
                    continue

                logger.debug(f"Servers with mod: {servers_with_mod}")

                local_time = ZoneInfo("localtime")
                time_updated = datetime.datetime.fromtimestamp(
                    item["time_updated"], tz=local_time
                )
                formatted_time = time_updated.strftime("%b %d @ %I:%M%p %Z")

                guild = self.bot.get_guild(MY_GUILD)
                if not guild:
                    logger.warning("Unable to get guild")
                    continue
                ar = guild.get_role(PZ_ADMIN_ROLE_ID)
                if not ar:
                    logger.warning("Unable to get admin role id")
                    continue
                admin_role = ar.mention

                update_msg = (
                    f"{admin_role} A mod has updated on **{'** and **'.join(servers_with_mod)}**!\n"
                    f"Title: {item['title'].strip()}\n"
                    f"Updated: {formatted_time}\n"
                    f"https://steamcommunity.com/sharedfiles/filedetails/?id={item['publishedfileid']}"
                )

                chan = self.bot.get_channel(ANNOUNCE_CHANNEL)
                if not chan:
                    logger.warning("Unable to get discord channel.")
                    continue
                if not isinstance(chan, discord.TextChannel):
                    logger.warning("Chan is not TextChannel?")
                    continue

                await chan.send(update_msg)

                logger.info("A mod has updated!")
                logger.info(f"title: {item['title'].strip()}")
                logger.info(f"updated: {formatted_time}")
                logger.info(
                    f"https://steamcommunity.com/sharedfiles/filedetails/?id={item['publishedfileid']}"
                )

                tasks = [
                    auto_restart.auto_restart(
                        chan,
                        server_name,
                        f"Auto restart triggered for the **{server_name}** server. Restarting in 5min.",
                    )
                    for server_name in servers_with_mod
                ]
                try:
                    results = await asyncio.gather(*tasks)
                    logger.debug(f"Results: {results}")

                    if not self.check_workshop_errors.is_running():
                        self.error_check_counter = 0
                        self.check_workshop_errors.start()
                        logger.info("Started workshop error scanning task")
                    else:
                        logger.info("Workshop error scanning already running")
                except Exception as e:
                    logger.error(f"An unexpected exception occurred: {e}")

    @tasks.loop(minutes=1)
    async def check_workshop_errors(self):
        """Scans all modded server logs for workshop errors and restarts affected servers."""
        paths = await server_setting_paths()
        modded_servers = await get_servers_workshop_ids(paths)

        if not modded_servers:
            logger.info("No modded servers found. Stopping workshop error scan.")
            self.check_workshop_errors.cancel()
            return

        all_servers_complete = True

        for server_name, workshop_ids in modded_servers.items():
            if server_name not in self.server_error_counters:
                self.server_error_counters[server_name] = 0

            if self.server_error_counters[server_name] >= 5:
                logger.debug(f"Server {server_name} error scan complete (5 iterations)")
                continue

            self.server_error_counters[server_name] += 1
            logger.debug(
                f"Workshop error scan for {server_name}: iteration {self.server_error_counters[server_name]}/5"
            )

            if server_name not in Config.SYSTEM_USERS:
                logger.warning(
                    f"Server {server_name} not found in configuration. Skipping."
                )
                continue

            system_user = Config.SYSTEM_USERS[server_name]
            log_path = f"/home/{system_user}/log/console/pzserver-console.log"
            output_path = f"/home/{system_user}/pz_scripts/workshop_id.txt"

            try:
                error_ids = await extract_workshop_ids(log_path)

                if error_ids:
                    logger.warning(f"Found workshop errors on {server_name}: {error_ids}")

                    await write_ids_to_file(error_ids, output_path)
                    logger.info(f"Workshop IDs written to {output_path}")

                    chan = self.bot.get_channel(ANNOUNCE_CHANNEL)
                    if chan and isinstance(chan, discord.TextChannel):
                        await chan.send(
                            f"🚨 **Workshop errors detected on {server_name}!**\n"
                            f"Problematic workshop IDs: {', '.join(error_ids)}\n"
                            f"Performing immediate server restart to apply fix..."
                        )

                    restart_success = await restart_zomboid_server(system_user)

                    if chan and isinstance(chan, discord.TextChannel):
                        if restart_success:
                            await chan.send(
                                f"✅ **{server_name}** restarted successfully and will be back up soon."
                            )
                        else:
                            await chan.send(f"❌ Failed to restart **{server_name}**!")

                    self.server_error_counters[server_name] = 0
                else:
                    logger.debug(f"No workshop errors found on {server_name}")
                    self.server_error_counters[server_name] = 0

            except FileNotFoundError:
                logger.warning(
                    f"Log file not found for {server_name}: {log_path}. Skipping."
                )
            except Exception as e:
                logger.error(
                    f"Error checking workshop errors for {server_name}: {e}. Skipping."
                )

            all_servers_complete = False

        if all_servers_complete:
            self.check_workshop_errors.cancel()
            logger.info("Workshop error scan completed (all servers)")
            return

        active_servers = sum(
            1 for c in self.server_error_counters.values() if c > 0 and c < 5
        )
        if active_servers == 0:
            self.check_workshop_errors.cancel()
            logger.info("Workshop error scan completed (no active errors)")

