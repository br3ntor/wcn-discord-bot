import logging
import os

from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    from bot import bot

    token = os.getenv("TOKEN")
    if token is None:
        print("Token is None")
        exit(1)

    bot.run(token)
