import logging
from datetime import time
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from src.config import Config
from src.services.chat_transcript import build_general_transcript
from src.services.llm import summarize_chat

logger = logging.getLogger(__name__)

PACIFIC = ZoneInfo("America/Los_Angeles")
DIGEST_TIMES = [time(hour=8, tzinfo=PACIFIC), time(hour=20, tzinfo=PACIFIC)]
DIGEST_WINDOW_HOURS = 12
MAX_EMBED_DESCRIPTION = 4000


class AISummaryCog(commands.Cog):
    """Posts AI-generated digests of in-game global chat to Discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        if not Config.OPENROUTER_API_KEY:
            logger.warning(
                "OPENROUTER_API_KEY not set, AI summary digest loop disabled"
            )
            return
        self.digest_loop.start()

    async def cog_unload(self):
        if self.digest_loop.is_running():
            self.digest_loop.cancel()

    def _summary_channel_id(self) -> int:
        return Config.AI_SUMMARY_CHANNEL or Config.ANNOUNCE_CHANNEL

    @tasks.loop(time=DIGEST_TIMES)
    async def digest_loop(self):
        channel = self.bot.get_channel(self._summary_channel_id())
        if not isinstance(channel, discord.TextChannel):
            logger.error(
                "AI summary channel %s not found, skipping digest run",
                self._summary_channel_id(),
            )
            return

        for server in Config.SERVER_DATA:
            try:
                await self._post_server_digest(
                    channel, server["system_user"], server["server_name"]
                )
            except Exception:
                logger.exception("AI digest failed for %s", server["server_name"])

    async def _post_server_digest(
        self, channel: discord.TextChannel, system_user: str, server_name: str
    ):
        transcript = await build_general_transcript(system_user, DIGEST_WINDOW_HOURS)
        if not transcript:
            logger.info(
                "No general chat on %s in the last %sh, skipping digest",
                server_name,
                DIGEST_WINDOW_HOURS,
            )
            return

        summary = await summarize_chat(transcript, server_name, DIGEST_WINDOW_HOURS)
        if not summary:
            return

        embed = discord.Embed(
            title=f"{server_name} — community digest",
            description=summary[:MAX_EMBED_DESCRIPTION],
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"Global chat, last {DIGEST_WINDOW_HOURS}h")
        await channel.send(embed=embed)
        logger.info("Posted AI digest for %s", server_name)

    @digest_loop.before_loop
    async def before_digest_loop(self):
        await self.bot.wait_until_ready()
