import logging

import discord

from src.config import Config

# Initialize config before importing bot (which imports cogs/services
# that reference Config attributes at module scope).
Config.init()

from src.bot import bot  # noqa: E402

if __name__ == "__main__":
    # Discord handles its own loggers (stays at INFO by default)
    discord.utils.setup_logging(root=False)

    # Our loggers get their own handler, isolated from discord's
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)-8s] %(name)s: %(message)s"))
    src_logger = logging.getLogger("src")
    src_logger.setLevel(logging.DEBUG)
    src_logger.addHandler(handler)

    logger = logging.getLogger(__name__)
    logger.info("Starting WCN-DiscordBot")

    Config.validate()

    token = Config.DISCORD_TOKEN
    if token is None:
        raise SystemExit("DISCORD_TOKEN is missing. Exiting.")

    bot.run(token)
