import json
from datetime import datetime

import discord
from aiohttp import web
from discord.ext import commands

# from bot import MyBot
from config import Config
from lib.local_db import add_donation

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
WEBHOOK_SECRET = Config.WEBHOOK_SECRET
WEBHOOK_PATH = "/hook"


def get_last_14th() -> datetime:
    """Get the date of the most recent 14th (either current month or previous month)."""
    today = datetime.now()

    # If we're before the 14th of current month, get previous month's 14th
    if today.day < 14:
        # If we're in January, go back to December
        if today.month == 1:
            return datetime(today.year - 1, 12, 14)
        else:
            return datetime(today.year, today.month - 1, 14)
    # If we're after the 14th, use current month's 14th
    else:
        return datetime(today.year, today.month, 14)


class WebhookCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def donation_goal_message(self):
        # Get the most recent 14th date
        last_14th = get_last_14th()

        # Get all donations since that date
        donations = await get_donations_since(last_14th)

    # Experimenting with using the underscore for private methods
    async def _handle_webhook(self, request):
        """Handles the incoming Ko-fi webhook."""
        data = await request.post()
        # Process the webhook data here
        donation = json.loads(data["data"])
        verification_token = donation["verification_token"]
        is_public = donation["is_public"]
        donator = donation["from_name"]
        url = donation["url"]
        email = donation["email"]

        # Publish donation action, thank user by given name
        if verification_token == WEBHOOK_SECRET and is_public:
            thanks_msg1 = (
                f"🎉 Thank you **{donator}** for your generous donation! 💸\n{url}"
            )

            # Send thankyou message to discord
            discord_channel = self.bot.get_channel(948548630439165956)
            if isinstance(discord_channel, discord.TextChannel):
                await discord_channel.send(thanks_msg1)
            else:
                # TODO: Learn how to use the damn built in logging module
                print(
                    "WARNING: Discord message not sent. discord_channel is not a TextChannel."
                )
            print(thanks_msg1)

            # Add the donation to the database
            added_to_db = await add_donation(donator, email, donation["amount"])
            if not added_to_db:
                print("ERROR: Donation was not added to the db.")

        # Thanks when donator doesn't give name.
        elif verification_token == WEBHOOK_SECRET and not is_public:
            print("🎉 Thank you anonymous member for your generous donation! 💸❔")
        else:
            print("Verification token not valid?")
            print(data)
        return web.Response()

    @commands.Cog.listener()
    async def on_ready(self):
        print("Bot is ready, starting webhook listener on port 5000...")

        app = web.Application()
        app.router.add_post(WEBHOOK_PATH, self._handle_webhook)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(
            runner, "127.0.0.1", 5000
        )  # Change the IP and port as needed
        await site.start()
