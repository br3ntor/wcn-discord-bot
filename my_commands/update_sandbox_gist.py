import os
import aiohttp
import discord
from discord import app_commands


GITHUB_PAT = os.getenv("GITHUB_PAT")

server_gist_id = "392d6ae26f627b3ee8c9cacb4111d035"


def get_sandboxsettings():
    """Returns text content of servers sandbox-settings file."""
    file_path = "/home/pzserver/Zomboid/Server/pzserver_SandboxVars.lua"
    with open(file_path) as f:
        return f.read()


async def update_gist(payload: str) -> None:
    """Update gist with current server sandbox settings."""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    payload = {
        "description": "West Coast Noobs sandbox settings.",
        "files": {"pzserver_SandboxVars.lua": {"content": payload}},
    }

    async with aiohttp.ClientSession() as session:
        url = f"https://api.github.com/gists/{server_gist_id}"
        async with session.patch(url, headers=headers, json=payload) as resp:
            print(resp.status)
            # print(await resp.text())


@app_commands.command()
async def update_sandbox_gist(interaction: discord.Interaction):
    """Updates server sandbox settings gist."""
    payload = get_sandboxsettings()
    await update_gist(payload)

    url = f"https://gist.github.com/br3ntor/{server_gist_id}"

    await interaction.response.send_message(
        f"View the pzserver server's sandbox settings.\n{url}"
    )
