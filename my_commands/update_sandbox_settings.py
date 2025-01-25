import aiohttp
import discord
from discord import app_commands

from config import Config

GITHUB_PAT = Config.GITHUB_PAT
SERVER_DATA = Config.SERVER_DATA


def get_sandboxsettings(server: str):
    """Returns text content of servers sandbox-settings file."""
    file_path = f"/home/{server}/Zomboid/Server/pzserver_SandboxVars.lua"
    with open(file_path) as f:
        return f.read()


async def update_gist(
    sandboxsettings: str, server_gist_id: str, server_name: str
) -> None:
    """Update gist with current server sandbox settings."""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    payload = {
        "description": f"{server_name} sandbox settings.",
        "files": {f"{server_name}_SandboxVars.lua": {"content": sandboxsettings}},
    }

    async with aiohttp.ClientSession() as session:
        url = f"https://api.github.com/gists/{server_gist_id}"
        async with session.patch(url, headers=headers, json=payload) as resp:
            print(resp.status)
            # print(await resp.text())


@app_commands.command(name="sandbox_settings")
async def update_sandbox_settings(interaction: discord.Interaction):
    """Updates server sandbox settings gist."""
    links = []
    for server in SERVER_DATA:
        if (
            server["gists"] is not None
            and "sandbox" in server["gists"]
            and server["gists"]["sandbox"]
        ):
            payload = get_sandboxsettings(server["system_user"])
            await update_gist(
                payload, server["gists"]["sandbox"], server["system_user"]
            )
            links.append(
                f"**{server['server_name']}**: https://gist.github.com/br3ntor/{server['gists']['sandbox']}"
            )

    formatted_links = "\n".join(links)
    await interaction.response.send_message(f"Sandbox settings:\n{formatted_links}")
