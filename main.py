import logging

from dotenv import load_dotenv

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Loading env...")
    load_dotenv()
    from src.config import Config

    Config.validate()

    from src.bot import bot

    token = Config.DISCORD_TOKEN
    if token is None:
        raise SystemExit("DISCORD_TOKEN is missing. Exiting.")

    bot.run(token)
