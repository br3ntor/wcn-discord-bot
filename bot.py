import discord
from discord import app_commands
from discord.ext import commands

# My command modules folder
import my_commands
from config import Config
from my_cogs.tasks import TasksCog
from my_cogs.webhook import WebhookCog

MY_GUILD = discord.Object(id=int(Config.MY_GUILD))


class MyBot(commands.Bot):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(command_prefix="-", intents=intents)
        # A CommandTree is a special type that holds all the application command
        # state required to make it work. This is a separate class because it
        # allows all the extra state to be opt-in.
        # Whenever you want to work with application commands, your tree is used
        # to store and work with them.
        # Note: When using commands.Bot instead of discord.Client, the bot will
        # maintain its own tree instead.
        # self.tree = app_commands.CommandTree(self)

    # In this basic example, we just synchronize the app commands to one guild.
    # Instead of specifying a guild to every command, we copy over our global
    # commands instead. By doing so, we don't have to wait up to an hour until
    # they are shown to the end-user.
    async def setup_hook(self):
        for command_name in my_commands.__all__:
            attr = getattr(my_commands, command_name)
            if isinstance(attr, app_commands.Command) or isinstance(
                attr, app_commands.Group
            ):
                self.tree.add_command(attr)

        await self.add_cog(TasksCog(self))
        await self.add_cog(WebhookCog(self))
        # This copies the global commands over to your guild.
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)


intents = discord.Intents.all()
bot = MyBot(intents=intents)


# NOTE: I wonder how to keep these in their own file?
@bot.event
async def on_ready():
    # Another way to make pyright happy, still getting use to this
    # if client.user is not None:
    # I like this assert way, i know theres some others too.
    assert bot.user is not None
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")


# Error handler for application command errors
@bot.tree.error
async def on_application_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.MissingRole):
        await interaction.response.send_message(
            "You do not have the required role to use this command.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "An error occurred while processing your command, check logs.",
            ephemeral=True,
        )
    print(f"AppCommandError: {error}")
