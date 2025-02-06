import asyncio
import socket

from steam.webapi import WebAPI

from config import Config

STEAM_KEY = Config.STEAM_KEY


async def get_workshop_items(workshop_ids: list[str]) -> list:
    """Calls steam api to get mod data."""
    try:
        api = await asyncio.to_thread(WebAPI, STEAM_KEY)

        # Changing all string ids to ints
        # Before they were all sent as strings and a mod author using fancy number "font"
        # broke it, actually they didnt use a font but a Mathematical Alphanumeric Symbol
        int_ids = [int(id) for id in workshop_ids]

        item_count = len(int_ids)

        steam_remote_storage = getattr(api, "ISteamRemoteStorage", None)
        if steam_remote_storage is None:
            raise AttributeError(
                "ISteamRemoteStorage is not available on the WebAPI instance."
            )

        workshop_items = await asyncio.to_thread(
            steam_remote_storage.GetPublishedFileDetails,
            itemcount=item_count,
            publishedfileids=int_ids,
        )
    except socket.timeout:
        print("Bruh, steam network might be taking a shit.")
        return []
    except Exception as e:
        print(f"An error occurred while fetching workshop items: {e}")
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
