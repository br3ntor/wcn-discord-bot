import logging
import os

from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    from bot import client

    client.run(os.getenv("TOKEN"))
