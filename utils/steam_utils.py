import os

from steam.webapi import WebAPI

from utils.server_helpers import get_all_workshop_ids

STEAM_KEY = os.getenv("STEAM_WEBAPI")


async def get_workshop_items() -> list:
    """Calls steam api to get mod data."""
    api = WebAPI(STEAM_KEY)

    workshop_ids = await get_all_workshop_ids()

    item_count = len(workshop_ids)

    workshop_items = api.ISteamRemoteStorage.GetPublishedFileDetails(
        itemcount=item_count, publishedfileids=workshop_ids
    )

    items = workshop_items["response"]["publishedfiledetails"]
    print(f"Found this many workshop_items: {len(items)}")
    return items
