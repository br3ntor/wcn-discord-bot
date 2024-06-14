import json
import os

from aiohttp import web
from discord.ext import commands

ANNOUNCE_CHANNEL = int(os.getenv("ANNOUNCE_CHANNEL", 0))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
WEBHOOK_PATH = "/hook"


class WebhookCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def handle_webhook(self, request):
        data = await request.post()
        # Process the webhook data here
        donation = json.loads(data["data"])
        verification_token = donation["verification_token"]
        is_public = donation["is_public"]
        donator = donation["from_name"]
        url = donation["url"]
        if verification_token == WEBHOOK_SECRET and is_public:
            thanks_msg1 = (
                f"🎉 Thank you **{donator}** for your generous donation! 💸\n{url}"
            )
            spam = self.bot.get_channel(ANNOUNCE_CHANNEL)
            await spam.send(thanks_msg1)
            print(thanks_msg1)
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
        app.router.add_post(WEBHOOK_PATH, self.handle_webhook)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(
            runner, "127.0.0.1", 5000
        )  # Change the IP and port as needed
        await site.start()
