import logging
import time
import traceback
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks
from tabulate import tabulate

from src.config import Config
from src.services.server import get_servers_max_players, server_setting_paths
from src.services.steam import get_steam_playerlist

logger = logging.getLogger(__name__)


class PlayerlistCog(commands.Cog):
    """Cog for periodically updating the playerlist message in Discord threads."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @tasks.loop(seconds=60)
    async def update_loop(self):
        ip = Config.SERVER_PUB_IP
        if not isinstance(ip, str):
            logger.warning("SERVER_PUB_IP is not a string. Skipping loop.")
            return

        paths = await server_setting_paths()
        max_players = await get_servers_max_players(paths)

        for srv_info in Config.SERVER_DATA:
            if not srv_info["discord_playerlist"]:
                continue

            thread_id = srv_info["discord_playerlist"]["thread_id"]
            msg_id = srv_info["discord_playerlist"]["message_id"]

            thread = self.bot.get_channel(thread_id)
            if not thread or not isinstance(
                thread, (discord.Thread, discord.TextChannel)
            ):
                logger.warning(
                    f"Could not find thread {thread_id} for {srv_info['server_name']}"
                )
                continue

            # Quick and dirty for setup
            if msg_id == 123:
                await thread.send("Initial msg copy this id")
                return

            server_max = max_players.get(srv_info["system_user"], 64)

            try:
                data = await get_steam_playerlist(
                    ip, int(srv_info["port"]), srv_info["server_name"]
                )

                msg = await thread.fetch_message(msg_id)

                title = f"{data['server_name']} - {data['player_count']} Players"
                if server_max is not None:
                    title = f"{data['server_name']} - {data['player_count']}/{server_max} Players"

                embed = discord.Embed(
                    title=title,
                    color=(
                        discord.Color.green()
                        if data["player_count"] > 0
                        else discord.Color.red()
                    ),
                )

                if data["error"]:
                    embed.description = f"⚠️ {data['error']}"
                elif data["player_count"] == 0:
                    embed.description = "No players online"
                else:
                    player_table = tabulate(
                        data["players"], headers=["Name", "Duration"]
                    )
                    content = f"```\n{player_table}\n```"

                    if len(content) > 4096:
                        truncated_players = data["players"][:40]
                        player_table = tabulate(
                            truncated_players, headers=["Name", "Duration"]
                        )
                        content = f"```\n{player_table}\n```\n*...and {data['player_count'] - 40} more players*"

                    embed.description = content

                embed.timestamp = datetime.now(timezone.utc)

                await msg.edit(
                    content=f"Last updated: <t:{int(time.time())}:R>", embed=embed
                )
                logger.info(
                    f"Successfully updated player list for {srv_info['server_name']}"
                )

            except discord.NotFound:
                logger.warning(
                    f"Message {msg_id} not found in {srv_info['server_name']}"
                )
            except Exception as e:
                logger.error(
                    f"Error updating {srv_info['server_name']}: {e}\n{traceback.format_exc()}"
                )

    @update_loop.before_loop
    async def before_update_loop(self):
        """Wait until the bot's internal cache is ready before starting the loop."""
        await self.bot.wait_until_ready()

    async def cog_load(self):
        """Auto-start the loop when the Cog is loaded."""
        if not self.update_loop.is_running():
            self.update_loop.start()

    async def cog_unload(self):
        """Stop the loop if the Cog is unloaded to prevent 'ghost' background tasks."""
        self.update_loop.cancel()
