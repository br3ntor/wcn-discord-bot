import json
import logging

import discord
from aiohttp import web
from discord.ext import commands

from src.config import Config
from src.services.bot_db import add_donation
from src.utils.helpers import (
    KOFI_GOAL_URL,
    get_monthly_donation_progress,
    show_donation_progress,
)

logger = logging.getLogger(__name__)

# TODO: switch to Config.ANNOUNCE_CHANNEL when moving off the test server
ANNOUNCE_CHANNEL_ID = 948548630439165956
WEBHOOK_SECRET = Config.WEBHOOK_SECRET
WEBHOOK_PATH = "/hook"


class KoFiDonationCog(commands.Cog):
    """Cog for handling Ko-fi donation webhooks and posting them to Discord."""

    def __init__(self, bot):
        self.bot = bot
        self._webhook_runner: web.AppRunner | None = None
        if not Config.WEBHOOK_SECRET:
            raise ValueError("WEBHOOK_SECRET env var is required for KoFiDonationCog")

    async def cog_unload(self):
        if self._webhook_runner is not None:
            await self._webhook_runner.cleanup()
            self._webhook_runner = None

    @commands.Cog.listener()
    async def on_ready(self):
        """Starts the Ko-fi webhook HTTP listener on port 5000."""
        # on_ready can fire again on Discord reconnects; only start once.
        if self._webhook_runner is not None:
            return

        app = web.Application()
        app.router.add_post(WEBHOOK_PATH, self._handle_kofi_donation)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 5000)
        await site.start()
        self._webhook_runner = runner
        logger.info("Ko-fi webhook listener started on 127.0.0.1:5000%s", WEBHOOK_PATH)

    async def _handle_kofi_donation(self, request):
        """Handles incoming Ko-fi webhook for donation events."""
        try:
            data = await request.post()
            donation = json.loads(data["data"])
            amount = float(donation.get("amount", 0))
            donator = donation.get("from_name", "Someone")
            email = donation.get("email", "")
        except Exception:
            logger.exception("Failed to parse Ko-fi webhook payload")
            logger.debug("%s", request)
            return web.Response()

        if donation.get("verification_token") != WEBHOOK_SECRET:
            logger.warning("Ko-fi webhook: verification token not valid")
            logger.debug("%s", data)
            return web.Response()

        # Publish donation action, thank user by given name
        if donation.get("is_public"):
            thanks_msg = (
                f"🎉 Thank you **{donator}** for your generous donation! 💸\n"
                f"{KOFI_GOAL_URL}"
            )
        # Thanks when donator doesn't give name.
        else:
            thanks_msg = (
                "🎉 Thank you anonymous member for your generous donation! 💸❔"
            )

        discord_channel = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if not isinstance(discord_channel, discord.TextChannel):
            logger.warning(
                "Ko-fi webhook: could not resolve TextChannel %s", ANNOUNCE_CHANNEL_ID
            )
            return web.Response()

        try:
            await discord_channel.send(thanks_msg)
            logger.info(thanks_msg)

            # Add the donation to the database
            if not await add_donation(donator, email, amount):
                logger.error("ERROR: Donation was not added to the db.")

            current_amount, goal_amount = await get_monthly_donation_progress()
            donation_progress = show_donation_progress(current_amount, goal_amount)

            # Ko-fi's public goal page can lag behind this webhook; our progress
            # bar above is computed from our own db and is already accurate. If
            # the page still looks stale to viewers, uncomment to let it catch up:
            # await asyncio.sleep(60)

            await discord_channel.send(donation_progress)
        except Exception:
            logger.exception("Failed to process Ko-fi donation")

        return web.Response()
