import logging
import discord

from dotenv import load_dotenv

if __name__ == "__main__":
    formatter = logging.Formatter('[%(levelname)-8s] %(name)s: %(message)s')
    discord.utils.setup_logging(formatter=formatter, level=logging.INFO, root=True)
    
    logger = logging.getLogger(__name__)
    logger.info("Loading env...")
    load_dotenv()
    from src.config import Config

    Config.validate()

    from src.bot import bot

    token = Config.DISCORD_TOKEN
    if token is None:
        raise SystemExit("DISCORD_TOKEN is missing. Exiting.")

    bot.run(token)
