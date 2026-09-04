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
    servers_with_mod_update,
)
from src.services.steam import get_workshop_items

logger = logging.getLogger(__name__)

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
MY_GUILD = Config.MY_GUILD
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID


async def _run_auto_restart(
    channel: discord.TextChannel, server_name: str, init_msg: str, reason: str = ""
) -> None:
    """Runs auto_restart in the background, logging any failures."""
    try:
        await auto_restart.auto_restart(channel, server_name, init_msg, reason)
    except Exception:
        logger.exception("Auto restart task for %s failed", server_name)


class ModUpdatesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mod_update_times: dict[str, int] = {}
        self.workshop_ids: list[str] | None = None
        self._restart_tasks: set[asyncio.Task] = set()

    async def cog_unload(self):
        self.check_mod_updates.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Starting mod updates tasks...")
        self.check_mod_updates.start()

    @tasks.loop(minutes=5)
    async def check_mod_updates(self):
        """Checks if mods have been updated since last check.
        Sends ping to admins if there are updates."""
        logger.debug("Checking for mod updates...")

        # Dynamically fetch the latest workshop IDs from running servers
        current_workshop_ids = await combine_servers_workshop_ids()

        if not current_workshop_ids:
            logger.info("No workshop IDs found on any running servers, skipping check")
            return

        self.workshop_ids = current_workshop_ids
        workshop_items = await get_workshop_items(self.workshop_ids)

        # Track new mods discovered during this check
        new_mods_count = 0

        # Collect every mod that updated and is used by a running server, so
        # all updates in one pass can share a single restart per server.
        updated_mods: list[tuple[dict, list[str]]] = []

        for item in workshop_items:
            if "title" not in item:
                logger.warning(
                    "Skipping item %s in update check — missing title (result=%s)",
                    item.get("publishedfileid"),
                    item.get("result"),
                )
                continue

            workshop_id = item["publishedfileid"]

            # If we've never seen this mod before (newly added to config)
            if workshop_id not in self.mod_update_times:
                new_mods_count += 1
                self.mod_update_times[workshop_id] = item["time_updated"]
                continue

            stored_time = self.mod_update_times[workshop_id]

            if item["time_updated"] > stored_time:
                self.mod_update_times[workshop_id] = item["time_updated"]

                servers_with_mod = await servers_with_mod_update(
                    item["publishedfileid"]
                )

                if not servers_with_mod:
                    logger.debug(
                        f"Mod {workshop_id} updated, but no running servers are using it. Skipping announcement."
                    )
                    continue

                logger.debug(f"Servers with mod: {servers_with_mod}")
                updated_mods.append((item, servers_with_mod))

        if new_mods_count > 0:
            logger.info("Recording initial timestamps for %d new mods", new_mods_count)

        if not updated_mods:
            return

        guild = self.bot.get_guild(MY_GUILD)
        if not guild:
            logger.warning("Unable to get guild")
            return
        ar = guild.get_role(PZ_ADMIN_ROLE_ID)
        if not ar:
            logger.warning("Unable to get admin role id")
            return
        admin_role = ar.mention

        chan = self.bot.get_channel(ANNOUNCE_CHANNEL)
        if not isinstance(chan, discord.TextChannel):
            logger.warning("Unable to get discord channel.")
            return

        local_time = ZoneInfo("localtime")

        # Announce each updated mod
        for item, servers_with_mod in updated_mods:
            time_updated = datetime.datetime.fromtimestamp(
                item["time_updated"], tz=local_time
            )
            formatted_time = time_updated.strftime("%b %d @ %I:%M%p %Z")

            update_msg = (
                f"{admin_role} A mod has updated on **{'** and **'.join(servers_with_mod)}**!\n"
                f"Title: {item['title'].strip()}\n"
                f"Updated: {formatted_time}\n"
                f"https://steamcommunity.com/sharedfiles/filedetails/?id={item['publishedfileid']}"
            )

            await chan.send(update_msg)

            logger.info(
                f"Mod updated: {item['title'].strip()} ({item['publishedfileid']}) — {formatted_time}"
            )

        # Queue a single restart per server for the whole batch of updates.
        mods_per_server: dict[str, int] = {}
        for _, servers_with_mod in updated_mods:
            for server_name in servers_with_mod:
                mods_per_server[server_name] = mods_per_server.get(server_name, 0) + 1

        for server_name, count in mods_per_server.items():
            mod_word = "update" if count == 1 else "updates"
            reason = f"{count} mod {mod_word}" if count > 1 else "a mod update"
            init_msg = (
                f"Auto restart triggered for the **{server_name}** server. "
                f"{count} mod {mod_word} detected. Restarting in 5min."
            )

            task = asyncio.create_task(
                _run_auto_restart(chan, server_name, init_msg, reason)
            )
            self._restart_tasks.add(task)
            task.add_done_callback(self._restart_tasks.discard)
