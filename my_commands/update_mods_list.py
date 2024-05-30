import os

import discord
import requests
from discord import app_commands

from utils.steam_utils import get_workshop_items

# Only need these for testing single function in here
# from dotenv import load_dotenv
# load_dotenv()


STEAM_KEY = os.getenv("STEAM_WEBAPI")
GITHUB_PAT = os.getenv("GITHUB_PAT")

server_gist_id = "368a4d58ab96964575dfb292c597810c"


def parse_workshop_data(workshop_items: list) -> str:
    """Parse workshop mod data to markdown for gist."""
    mods = []
    for item in workshop_items["response"]["publishedfiledetails"]:
        if "title" in item:
            mods.append(
                f"[{item['title']}](https://steamcommunity.com/sharedfiles/filedetails/?id={item['publishedfileid']})\n\n"
            )

    mods.insert(0, f"**Mod Count: {len(mods)}**\n\n")

    # Need to make this into text again
    sorted_mods = "".join(sorted(mods))

    return sorted_mods


def update_gist(payload: str) -> None:
    """Update gist with new mods list!"""
    url = f"https://api.github.com/gists/{server_gist_id}"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    payload = {
        "description": "West Coast Noobs Mods List",
        "files": {"mods_list.md": {"content": payload}},
    }

    response = requests.patch(url, headers=headers, json=payload)
    print(response.status_code)
    # print(response.json())


@app_commands.command()
async def update_mods_list(
    interaction: discord.Interaction,
):
    """Updates the list of mods for a server."""
    url = f"https://gist.github.com/br3ntor/{server_gist_id}"

    # Updates the gist list based on server config file
    update_gist(
        parse_workshop_data(get_workshop_items()),
    )

    await interaction.response.send_message(f"List of mods on the server\n{url}")
