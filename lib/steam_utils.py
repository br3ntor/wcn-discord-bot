import asyncio
import socket
import time

from steam import game_servers as gs
from steam.webapi import WebAPI
from tabulate import tabulate

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
    servers_workshopids: dict[str, list[str]],
) -> dict[str, list[dict]]:
    """Returns a list of workshop mod data with server name as key"""
    server_data_mod_items: dict[str, list[dict]] = dict()
    for name, ids in servers_workshopids.items():
        server_data_mod_items.update({name: await get_workshop_items(ids)})

    return server_data_mod_items


def format_time(seconds: float) -> str:
    return time.strftime("%Hhr %Mmin", time.gmtime(seconds))


async def get_player_list_string(server_ip: str, port: int, server_name: str) -> str:
    """
    Queries a steam server and returns a formatted string table of players.
    """
    try:
        # Run the blocking steam query in a thread
        server_players = await asyncio.to_thread(gs.a2s_players, (server_ip, port))

        # Filter and Sort
        valid_players = [p for p in server_players if p["name"]]
        valid_players.sort(key=lambda x: x["duration"], reverse=True)

        if not valid_players:
            return f"I can see **0** players on the **{server_name}** server."

        # Format for Tabulate
        player_table = [[p["name"], format_time(p["duration"])] for p in valid_players]

        msg = f"I can see **{len(player_table)}** players on the **{server_name}** server.\n"
        msg += f"```\n{tabulate(player_table, headers=['Name', 'Duration'])}\n```"
        return msg

    except socket.timeout:
        return f"**{server_name}**: Connection timed out (Steam Network)."
    except Exception as e:
        return f"**{server_name}**: Error - {str(e)}"
