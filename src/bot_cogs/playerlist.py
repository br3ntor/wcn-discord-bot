import time

import discord
from discord.ext import commands, tasks

from src.config import Config
from src.utils.steam_utils import get_player_list_string


class PlayerlistCog(commands.Cog):
    """Cog for periodically updating the playerlist message in Discord threads."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @tasks.loop(seconds=60)
    async def update_loop(self):
        ip = Config.SERVER_PUB_IP
        if not isinstance(ip, str):
            print("[PlayerlistUpdater] SERVER_PUB_IP is not a string. Skipping loop.")
            return

        for srv_info in Config.SERVER_DATA:
            if not srv_info["discord_ids"]:
                continue

            thread_id = srv_info["discord_ids"]["thread_id"]
            msg_id = srv_info["discord_ids"]["message_id"]

            thread = self.bot.get_channel(thread_id)
            if not thread or not isinstance(
                thread, (discord.Thread, discord.TextChannel)
            ):
                print(
                    f"[PlayerlistUpdater] Could not find thread {thread_id} for {srv_info['server_name']}"
                )
                continue

            # Quick and dirty for setup
            if msg_id == 123:
                await thread.send("Initial msg copy this id")
                return

            try:
                content = await get_player_list_string(
                    ip, int(srv_info["port"]), srv_info["server_name"]
                )

                msg = await thread.fetch_message(msg_id)

                # Dynamic Discord timestamp (e.g., "5 minutes ago")
                timestamp = f"\n*Last updated: <t:{int(time.time())}:R>*"

                await msg.edit(content=f"{content}{timestamp}")

            except discord.NotFound:
                print(
                    f"[PlayerlistUpdater] Message {msg_id} not found in {srv_info['server_name']}"
                )
            except Exception as e:
                print(
                    f"[PlayerlistUpdater] Error updating {srv_info['server_name']}: {e}"
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
