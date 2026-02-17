import asyncio
import time

import a2s
import aiohttp
from tabulate import tabulate

from src.config import Config


async def get_workshop_items(workshop_ids: list[str]) -> list:
    """Calls steam api to get mod data."""
    try:
        int_ids = [int(id) for id in workshop_ids]
        item_count = len(int_ids)

        url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
        data = aiohttp.FormData()
        data.add_field("itemcount", str(item_count))
        for id in int_ids:
            data.add_field("publishedfileids", str(id))

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as resp:
                result = await resp.json()

        items = result["response"]["publishedfiledetails"]
    except asyncio.TimeoutError:
        print("Bruh, steam network might be taking a shit.")
        return []
    except Exception as e:
        print(f"An error occurred while fetching workshop items: {e}")
        return []

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
        players = await a2s.aplayers((server_ip, port))

        valid_players = [p for p in players if p.name]
        valid_players.sort(key=lambda x: x.duration, reverse=True)

        if not valid_players:
            return f"I can see **0** players on the **{server_name}** server."

        player_table = [[p.name, format_time(p.duration)] for p in valid_players]

        msg = f"I can see **{len(player_table)}** players on the **{server_name}** server.\n"
        msg += f"```\n{tabulate(player_table, headers=['Name', 'Duration'])}\n```"
        return msg

    except asyncio.TimeoutError:
        return f"**{server_name}**: Connection timed out (Steam Network)."
    except Exception as e:
        return f"**{server_name}**: Error - {str(e)}"
