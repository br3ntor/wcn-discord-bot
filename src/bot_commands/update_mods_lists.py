import aiohttp
import discord
from discord import app_commands

from src.config import Config
from src.services.server import get_servers_workshop_ids, server_setting_paths
from src.services.steam import get_servers_workshop_items

GITHUB_PAT = Config.GITHUB_PAT
SERVER_DATA = Config.SERVER_DATA


def parse_workshop_data(workshop_items: list) -> str:
    """Parse workshop mod data to markdown for gist."""
    mods = []
    for item in workshop_items:
        if "title" in item:
            mods.append(
                f"[{item['title']}](https://steamcommunity.com/sharedfiles/filedetails/?id={item['publishedfileid']})\n\n"
            )
        else:
            print(f"title is not in item:\n{item}")

    mods.insert(0, f"**Mod Count: {len(mods)}**\n\n")

    # Need to make this into text again
    sorted_mods = "".join(sorted(mods))

    return sorted_mods


async def update_gist(server_name: str, sorted_mods: str, server_gist_id: str) -> None:
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

    # Using aiohttp instead of requests for async HTTP requests
    async with aiohttp.ClientSession() as session:
        async with session.patch(url, headers=headers, json=payload) as response:
            print(response.status)


async def update_all_gists():
    settings_paths = await server_setting_paths()
    # This could be named better. This gets a dict obj which contains a servernmame key and list of ids for val
    servers_workshop_ids = await get_servers_workshop_ids(settings_paths)
    servers_mods = await get_servers_workshop_items(servers_workshop_ids)

    gist_links = []

    for zomboid_server in SERVER_DATA:
        system_user = zomboid_server["system_user"]
        server_name = zomboid_server["server_name"]

        # We need to make sure the config is correct and the server is in servers_mods
        if (
            system_user in servers_mods
            and zomboid_server["gists"] is not None
            and "modlist" in zomboid_server["gists"]
            and zomboid_server["gists"]["modlist"]
        ):

            data = parse_workshop_data(servers_mods[system_user])
            await update_gist(system_user, data, zomboid_server["gists"]["modlist"])
            link = (
                f"https://gist.github.com/br3ntor/{zomboid_server['gists']['modlist']}"
            )
            gist_links.append(f"**{server_name}**: {link}")
    return gist_links


@app_commands.command(name="mods_lists")
async def update_mods_lists(
    interaction: discord.Interaction,
):
    """Updates the list of mods for all server."""
    # I need to defer before this work then followup for response
    await interaction.response.defer()
    links = await update_all_gists()
    formatted_links = "\n".join(links)

    await interaction.followup.send(f"List of mods on the server(s)\n{formatted_links}")
