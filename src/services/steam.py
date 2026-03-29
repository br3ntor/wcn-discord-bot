import asyncio
import logging
import time

import a2s
import aiohttp
from tabulate import tabulate

from src.config import Config

logger = logging.getLogger(__name__)


async def get_workshop_items(workshop_ids: list[str]) -> list:
    """Calls steam api to get mod data."""
    try:
        int_ids = [int(id) for id in workshop_ids]
        item_count = len(int_ids)

        url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"

        data = {"itemcount": str(item_count)}
        for i, id in enumerate(int_ids):
            data[f"publishedfileids[{i}]"] = str(id)

        headers = {
            "User-Agent": "WCN-DiscordBot/1.0",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers) as resp:
                result = await resp.json()

        items = result["response"]["publishedfiledetails"]
    except asyncio.TimeoutError:
        logger.warning("Steam API timeout, network may be unavailable")
        return []
    except Exception as e:
        logger.error("An error occurred while fetching workshop items: %s", e)
        return []

    logger.debug("Found this many workshop_items: %s", len(items))
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


async def get_steam_playerlist(server_ip: str, port: int, server_name: str) -> dict:
    """
    Queries a steam server and returns structured player data.
    Returns a dict with keys: 'server_name', 'player_count', 'players', 'error'
    """
    try:
        players = await a2s.aplayers((server_ip, port))
        # print("[PLAYERLIST_RAW_DATA]:")
        # print(players)

        valid_players = [p for p in players if p.name]
        valid_players.sort(key=lambda x: x.duration, reverse=True)

        if not valid_players:
            return {
                "server_name": server_name,
                "player_count": 0,
                "players": [],
                "error": None,
            }

        player_data = [(p.name[:50], format_time(p.duration)) for p in valid_players]

        return {
            "server_name": server_name,
            "player_count": len(player_data),
            "players": player_data,
            "error": None,
        }

    except asyncio.TimeoutError:
        return {
            "server_name": server_name,
            "player_count": 0,
            "players": [],
            "error": "Connection timed out (Steam Network)",
        }
    except Exception as e:
        return {
            "server_name": server_name,
            "player_count": 0,
            "players": [],
            "error": str(e),
        }
