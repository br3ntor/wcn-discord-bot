import discord
from discord import app_commands
import os
import configparser
from steam.webapi import WebAPI
import requests

# Only need these for testing single function in here
# from dotenv import load_dotenv
# load_dotenv()


STEAM_KEY = os.getenv("STEAM_WEBAPI")
GITHUB_PAT = os.getenv("GITHUB_PAT")

server_gist_id = "368a4d58ab96964575dfb292c597810c"
# server_gist_ids = {
#     "light": "cec1edb58758a10a80e45bd27cbaee3e",
#     "heavy": "bd6cd4aa1fc6571260be63654f0995db",
# }


def get_mod_ids() -> list:
    """Returns a list of mod workshop ids for the server."""

    server_file = "/home/pzserver/Zomboid/Server/pzserver.ini"
    config = configparser.ConfigParser()

    # This seems to add the first line of the stream
    # to a header for an ini file, because the file
    # we are working with is not a proper ini file
    with open(server_file) as stream:
        config.read_string("[default]\n" + stream.read())

    workshop_ids = config["default"]["WorkshopItems"].split(";")
    print(f"Found this many workshopids: {len(workshop_ids)}")
    return workshop_ids


def get_mod_data(workshop_ids: list) -> list:
    """Calls steam api to get mod data."""
    api = WebAPI(STEAM_KEY)

    item_count = len(workshop_ids)

    workshop_items = api.ISteamRemoteStorage.GetPublishedFileDetails(
        itemcount=item_count, publishedfileids=workshop_ids
    )

    print(f"Found this many workshop_items: {len(workshop_items)}")
    return workshop_items


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
        parse_workshop_data(get_mod_data(get_mod_ids())),
    )

    await interaction.response.send_message(f"List of mods on the server\n{url}")
