import os
import aiohttp
import discord
from discord import app_commands


GITHUB_PAT = os.getenv("GITHUB_PAT")


server_gist_ids = {
    "light": "f6f6163393c21e92a5147b9e535eb0d3",
    "heavy": "cc814a2b2c1978ca119cb658bba3114d",
}


def get_sandboxsettings(server: str):
    """Returns text content of servers sandbox-settings file."""
    file_path = f"/home/pzserver{server}/Zomboid/Server/pzserver_SandboxVars.lua"
    with open(file_path) as f:
        return f.read()


async def update_gist(server_name: str, payload: str) -> None:
    """Update gist with current server sandbox settings."""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    payload = {
        "description": f"West Coast Noobs {server_name.title()} sandbox settings.",
        "files": {f"{server_name}_SandboxVars.lua": {"content": payload}},
    }

    async with aiohttp.ClientSession() as session:
        url = f"https://api.github.com/gists/{server_gist_ids[server_name]}"
        async with session.patch(url, headers=headers, json=payload) as resp:
            print(resp.status)
            # print(await resp.text())


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name="Light", value=1),
        app_commands.Choice(name="Heavy", value=2),
    ]
)
async def update_sandbox_gist(
    interaction: discord.Interaction,
    server: app_commands.Choice[int],
):
    """Updates server sandbox settings gist."""
    server_name = server.name.lower()
    payload = get_sandboxsettings(server_name)
    await update_gist(server_name, payload)

    url = f"https://gist.github.com/br3ntor/{server_gist_ids[server_name]}"

    await interaction.response.send_message(
        f"View the {server.name.lower()} server's sandbox settings.\n{url}"
    )
