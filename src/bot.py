import importlib
import logging

import discord
from discord import app_commands
from discord.ext import commands

import src.bot_commands as bot_commands
from src.config import Config
from src.services.bot_db import init_db

logger = logging.getLogger(__name__)


def import_cog(cog_name: str, class_name: str):
    """Dynamically import a cog class."""
    try:
        module = importlib.import_module(f"src.bot_cogs.{cog_name}")
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to import cog {cog_name}.{class_name}: {e}")
        return None


MY_GUILD = discord.Object(id=int(Config.MY_GUILD))


class WCNBot(commands.Bot):

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
        """Init the bots db and load our commands and cogs."""
        try:
            await init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.warning(f"Database initialization failed: {e}")

        for command_name in bot_commands.__all__:
            attr = getattr(bot_commands, command_name)
            if isinstance(attr, (app_commands.Command, app_commands.Group)):
                self.tree.add_command(attr)

        enabled_cogs = []
        for cog_name, cog_config in Config.COGS_CONFIG.items():
            if cog_config.get("enabled", False):
                cog_class = import_cog(cog_name, cog_config["class_name"])
                if cog_class:
                    try:
                        await self.add_cog(cog_class(self))
                        enabled_cogs.append(f"{cog_name} ({cog_config['description']})")
                    except Exception as e:
                        logger.error(f"Failed to load cog {cog_name}: {e}")

        if enabled_cogs:
            logger.info("Enabled Cogs:")
            for cog in enabled_cogs:
                logger.info(f"  - {cog}")
        else:
            logger.info("No cogs enabled in configuration")

        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)


intents = discord.Intents.all()
bot = WCNBot(intents=intents)


@bot.event
async def on_ready():
    if bot.user is None:
        raise RuntimeError("bot.user is None in on_ready (this should never happen)")
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")


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
    logger.error(f"AppCommandError: {error}")
