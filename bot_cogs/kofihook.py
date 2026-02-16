import json

import discord
from aiohttp import web
from discord.ext import commands

# from bot import MyBot
from config import Config
from lib.local_db import add_donation, get_total_donations_since
from lib.utils import get_last_occurrence_of_day, show_donation_progress

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
WEBHOOK_SECRET = Config.WEBHOOK_SECRET
WEBHOOK_PATH = "/hook"


class KoFiDonationCog(commands.Cog):
    """Cog for handling Ko-fi donation webhooks and posting them to Discord."""
    
    def __init__(self, bot):
        self.bot = bot

    # Experimenting with using the underscore for private methods
    async def _handle_kofi_donation(self, request):
        """Handles incoming Ko-fi webhook for donation events."""
        # Post request from ko-fi sent on donation
        # TODO: Needs error handling
        data = await request.post()
        # Process the webhook data here
        donation = json.loads(data["data"])
        verification_token = donation["verification_token"]
        is_public = donation["is_public"]
        donator = donation["from_name"]
        # I stopped sending this back because I think its just meant for the one who issued the donation.
        url = donation["url"]
        email = donation["email"]

        goal_url = "https://ko-fi.com/westcoastnoobs/goal"

        # Publish donation action, thank user by given name
        if verification_token == WEBHOOK_SECRET and is_public:
            thanks_msg = (
                f"🎉 Thank you **{donator}** for your generous donation! 💸\n{goal_url}"
            )
        # Thanks when donator doesn't give name.
        elif verification_token == WEBHOOK_SECRET and not is_public:
            thanks_msg = (
                "🎉 Thank you anonymous member for your generous donation! 💸❔"
            )
        else:
            print("Verification token not valid?")
            print(data)
            return web.Response()

        # Send thankyou message, and progress to discord
        discord_channel = self.bot.get_channel(ANNOUNCE_CHANNEL)
        if isinstance(discord_channel, discord.TextChannel):
            await discord_channel.send(thanks_msg)
            print(thanks_msg)

            # Add the donation to the database
            added_to_db = await add_donation(donator, email, donation["amount"])
            if not added_to_db:
                print("ERROR: Donation was not added to the db.")

            # Day that the bill hits
            last_6th = get_last_occurrence_of_day(6)
            donos_since_last_bill = await get_total_donations_since(last_6th)

            # Amount from patrons
            starting_amount = 5

            current_amount = donos_since_last_bill + starting_amount

            donation_progress = show_donation_progress(current_amount, 40)
            await discord_channel.send(donation_progress)

        else:
            # TODO: Learn how to use the damn built in logging module
            print(
                "WARNING: Discord message not sent. discord_channel is not a TextChannel."
            )

        return web.Response()

    @commands.Cog.listener()
    async def on_ready(self):
        """Starts the Ko-fi webhook HTTP listener on port 5000."""
        print("Bot is ready, starting Ko-fi webhook listener on port 5000...")

        app = web.Application()
        app.router.add_post(WEBHOOK_PATH, self._handle_kofi_donation)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(
            runner, "127.0.0.1", 5000
        )  # Change the IP and port as needed
        await site.start()
