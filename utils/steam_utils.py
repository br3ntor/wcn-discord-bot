import os

from steam.webapi import WebAPI

STEAM_KEY = os.getenv("STEAM_WEBAPI")


async def get_workshop_items(workshop_ids: list[str]) -> list:
    """Calls steam api to get mod data."""
    api = WebAPI(STEAM_KEY)

    # Changing all string ids to ints
    # Before they were all sent as strings and a mod author using fancy number "font"
    # broke it, actually they didnt use a font but a Mathematical Alphanumeric Symbol
    int_ids = [int(id) for id in workshop_ids]

    item_count = len(int_ids)

    try:
        workshop_items = api.ISteamRemoteStorage.GetPublishedFileDetails(
            itemcount=item_count,
            publishedfileids=int_ids,
        )
    except Exception as e:
        print(f"An error occurred while fetching workshop items: {e}")
        # Optionally, you might want to return an empty list or handle this error differently
        return []

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
