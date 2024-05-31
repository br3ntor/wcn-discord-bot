import os

import discord
import requests
from discord import app_commands

from config import SERVER_DATA
from utils.server_helpers import get_all_servers_and_workshop_ids, server_setting_paths
from utils.steam_utils import get_server_data_mod_items

STEAM_KEY = os.getenv("STEAM_WEBAPI")
GITHUB_PAT = os.getenv("GITHUB_PAT")


def parse_workshop_data(workshop_items: list) -> str:
    """Parse workshop mod data to markdown for gist."""
    mods = []
    for item in workshop_items:
        if "title" in item:
            mods.append(
                f"[{item['title']}](https://steamcommunity.com/sharedfiles/filedetails/?id={item['publishedfileid']})\n\n"
            )

    mods.insert(0, f"**Mod Count: {len(mods)}**\n\n")

    # Need to make this into text again
    sorted_mods = "".join(sorted(mods))

    return sorted_mods


def update_gist(server_name: str, sorted_mods: str, server_gist_id: str) -> None:
    """Update gist with new mods list!"""
    url = f"https://api.github.com/gists/{server_gist_id}"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    payload = {
        "description": f"West Coast Noobs {server_name} Mods List",
        "files": {f"{server_name}_mods.md": {"content": sorted_mods}},
    }

    response = requests.patch(url, headers=headers, json=payload)
    print(response.status_code)
    # print(response.json())


async def update_all_gists():
    settings_paths = await server_setting_paths()
    workshop_ids = await get_all_servers_and_workshop_ids(settings_paths)
    server_mods = await get_server_data_mod_items(workshop_ids)

    gist_links = []
    for zomboid_server in SERVER_DATA:
        if zomboid_server["gists"]["modlist"]:
            name = zomboid_server["name"]
            data = parse_workshop_data(server_mods[name])
            update_gist(name, data, zomboid_server["gists"]["modlist"])
            link = (
                f"https://gist.github.com/br3ntor/{zomboid_server['gists']['modlist']}"
            )
            gist_links.append(f"{name}: {link}")
    return gist_links


@app_commands.command()
async def update_mods_lists(
    interaction: discord.Interaction,
):
    """Updates the list of mods for all server."""
    links = await update_all_gists()
    formatted_links = "\n".join(links)

    await interaction.response.send_message(
        f"List of mods on the server(s)\n {formatted_links}"
    )
