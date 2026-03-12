import logging
import re

import discord
from discord.ext import commands

from src.config import Config
from src.services.log_watcher import RealTimeLogProcessor

logger = logging.getLogger(__name__)


def parse_zomboid_chat(log_line: str) -> str | None:
    if "Got message:" not in log_line:
        return None

    pattern = r"ChatMessage\{chat=(.*?), author='(.*?)', text='(.*?)'\}"

    match = re.search(pattern, log_line)

    if match is None:
        return None

    chat = match.group(1)
    author = match.group(2)
    text = match.group(3)

    if chat != "General":
        return None

    formatted_text = f"{author}: {text}"

    return formatted_text


class ChatLinkCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.monitor_tasks: list[RealTimeLogProcessor] = []

    async def cog_load(self):
        logger.info("ChatLinkCog loading...")
        await self.start_log_monitors()

    async def cog_unload(self):
        logger.info("ChatLinkCog unloading, stopping log monitors...")
        for monitor in self.monitor_tasks:
            if monitor.current_task:
                monitor.current_task.cancel()

    async def send_to_discord(self, message: str, channel_id: int):
        channel = self.bot.get_channel(channel_id)

        if not isinstance(channel, discord.TextChannel):
            logger.error(
                f"Channel with ID {channel_id} not found or is not a text channel. "
                f"Cannot send message: '{message}'."
            )
            return

        try:
            await channel.send(message)
        except Exception as e:
            logger.error(f"Failed to send message to channel {channel_id}: {e}")

    async def start_log_monitors(self):
        enabled_servers = []

        for server in Config.SERVER_DATA:
            logging_config = server.get("logging", {})
            if not logging_config.get("chat", False):
                continue

            channel_id = logging_config.get("channel_id")
            if not channel_id:
                logger.warning(
                    f"Server {server['server_name']} has logging.chat enabled but no logging.channel_id configured"
                )
                continue

            system_user = server["system_user"]
            server_name = server["server_name"]
            log_directory = f"/home/{system_user}/Zomboid/Logs/"
            log_pattern = "*chat.txt"

            async def make_callback(ch_id: int):
                async def callback(line: str):
                    parsed = parse_zomboid_chat(line)
                    if parsed:
                        await self.send_to_discord(parsed, ch_id)

                return callback

            callback = await make_callback(channel_id)

            monitor = RealTimeLogProcessor(
                log_directory, log_pattern, callback
            )

            self.monitor_tasks.append(monitor)
            enabled_servers.append(server_name)

            await monitor.start()

        if enabled_servers:
            logger.info(f"ChatLinkCog monitoring servers: {enabled_servers}")
        else:
            logger.info("ChatLinkCog loaded but no servers have log_chat enabled")
