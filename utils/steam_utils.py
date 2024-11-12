import os

from steam.webapi import WebAPI

STEAM_KEY = os.getenv("STEAM_WEBAPI")


async def get_workshop_items(workshop_ids: list[str]) -> list:
    """Calls steam api to get mod data."""
    api = WebAPI(STEAM_KEY)

    item_count = len(workshop_ids)

    workshop_items = api.ISteamRemoteStorage.GetPublishedFileDetails(
        itemcount=item_count, publishedfileids=workshop_ids
    )

    items = workshop_items["response"]["publishedfiledetails"]
    print(f"Found this many workshop_items: {len(items)}")
    return items


async def get_servers_workshop_items(
    servers_workshopids: dict[str, list[str]]
) -> dict[str, list[dict]]:
    """Returns a list of workshop mod data with server name as key"""
    server_data_mod_items: dict[str, list[dict]] = dict()
    for name, ids in servers_workshopids.items():
        server_data_mod_items.update({name: await get_workshop_items(ids)})

    return server_data_mod_items
