import importlib

import discord
from discord import app_commands
from discord.ext import commands

# My command modules folder
import src.bot_commands as bot_commands
from src.config import Config


def import_cog(cog_name: str, class_name: str):
    """Dynamically import a cog class."""
    try:
        module = importlib.import_module(f"src.bot_cogs.{cog_name}")
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        print(f"Failed to import cog {cog_name}.{class_name}: {e}")
        return None


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
        # Load application commands (existing logic)
        # and my old way to toggle commands on and off was just to comment
        # them out in __all__ of the __init__ thing, the way below through Congif
        # is preferred I think. TODO: Switch this to that!
        for command_name in bot_commands.__all__:
            attr = getattr(bot_commands, command_name)
            if isinstance(attr, app_commands.Command) or isinstance(
                attr, app_commands.Group
            ):
                self.tree.add_command(attr)

        # Check if any enabled cogs require database
        database_needed = any(
            cog_config.get("requires_database", False)
            for cog_config in Config.COGS_CONFIG.values()
            if cog_config.get("enabled", False)
        )

        database_available = False
        if database_needed:
            print("Database-dependent cogs detected, initializing database...")
            try:
                from src.services.bot_db import init_db

                await init_db()
                database_available = True
                print("✅ Database initialized successfully")
            except Exception as e:
                print(f"❌ Database initialization failed: {e}")
                print("⚠️  Database-dependent cogs will be disabled")

        # Load cogs based on configuration
        enabled_cogs = []
        for cog_name, cog_config in Config.COGS_CONFIG.items():
            if cog_config.get("enabled", False):
                # Check database dependency with our new tracking
                if cog_config.get("requires_database", False):
                    if not database_available:
                        print(f"Skipping {cog_name}: Database required but unavailable")
                        continue

                cog_class = import_cog(cog_name, cog_config["class_name"])
                if cog_class:
                    try:
                        await self.add_cog(cog_class(self))
                        enabled_cogs.append(f"{cog_name} ({cog_config['description']})")
                    except Exception as e:
                        print(f"Failed to load cog {cog_name}: {e}")

        # Log enabled cogs
        if enabled_cogs:
            print("Enabled Cogs:")
            for cog in enabled_cogs:
                print(f"  - {cog}")
        else:
            print("No cogs enabled in configuration")

        # Report database status
        if database_needed:
            status = "✅ Available" if database_available else "❌ Unavailable"
            print(f"Database Status: {status}")
            if database_available:
                db_dependent_enabled = sum(
                    1
                    for config in Config.COGS_CONFIG.values()
                    if config.get("enabled", False)
                    and config.get("requires_database", False)
                )
                print(f"Database-dependent cogs loaded: {db_dependent_enabled}")

        # Sync commands (existing logic)
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
