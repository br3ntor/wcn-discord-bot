import logging
import os

from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    from bot import client

    # Checking token type before using in client.run to make pyright happy
    token = os.getenv("TOKEN")
    if isinstance(token, str):
        client.run(token)
