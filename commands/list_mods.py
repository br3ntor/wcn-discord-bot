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

server_gist_ids = {
    "light": "cec1edb58758a10a80e45bd27cbaee3e",
    "heavy": "bd6cd4aa1fc6571260be63654f0995db",
}


def get_mod_ids(server: str) -> list:
    """Returns a list of mod workshop ids for a given server."""

    server_file = f"/home/pzserver{server}/Zomboid/Server/pzserver.ini"
    config = configparser.ConfigParser()

    # This seems to add the first line of the stream
    # to a header for an ini file, because the file
    # we are working with is not a proper ini file
    with open(server_file) as stream:
        config.read_string("[default]\n" + stream.read())

    workshop_items = config["default"]["WorkshopItems"].split(";")
    return workshop_items


def get_mod_data(workshop_ids: list) -> list:
    api = WebAPI(STEAM_KEY)

    item_count = len(workshop_ids)

    workshop_items = api.ISteamRemoteStorage.GetPublishedFileDetails(
        itemcount=item_count, publishedfileids=workshop_ids
    )

    return workshop_items


# TODO: Sort and add links
def parse_workshop_data(workshop_items: list) -> str:
    mods = ""
    for item in workshop_items["response"]["publishedfiledetails"]:
        if "title" in item:
            mods += item["title"] + "\n\n"
    return mods


def update_gist(server_name: str, payload: str) -> None:
    url = f"https://api.github.com/gists/{server_gist_ids[server_name]}"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    payload = {
        "description": f"West Coast Noobs {server_name.title()} Mods List.",
        "files": {f"{server_name}_mods_list.md": {"content": payload}},
    }

    response = requests.patch(url, headers=headers, json=payload)
    print(response.status_code)
    # print(response.json())


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name="Light", value=1),
        app_commands.Choice(name="Heavy", value=2),
    ]
)
async def list_mods(
    interaction: discord.Interaction,
    server: app_commands.Choice[int],
):
    """Prints a list of mods on the server."""
    server_name = server.name.lower()
    url = f"https://gist.github.com/br3ntor/{server_gist_ids[server_name]}"

    # Updates the gist list based on server config file
    update_gist(
        server_name,
        parse_workshop_data(get_mod_data(get_mod_ids(server.name.lower()))),
    )

    await interaction.response.send_message(
        f"List of mods on the {server.name.lower()}\n{url}"
    )
