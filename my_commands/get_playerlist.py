import time

import discord
from discord import app_commands
from steam import game_servers as gs
from tabulate import tabulate

from config import ALL_SERVER_NAMES, SERVER_DATA


def format_time(seconds: float) -> str:
    time_str = time.strftime("%Hhr %Mmin", time.gmtime(seconds))
    return time_str


def format_message(player_table: list, server: str) -> str:
    msg = f"""
I can see **{len(player_table)}** players on the **{server}**.
```md
{tabulate(player_table, headers=["Name", "Duration"])}
```
    """
    return msg


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(ALL_SERVER_NAMES)
    ]
)
@app_commands.describe(server="Which server?")
async def get_playerlist(
    interaction: discord.Interaction, server: app_commands.Choice[int]
):
    """Get a list of players on a server."""
    ip = next(srv["ip"] for srv in SERVER_DATA if srv["name"] == server.name)
    port = int(next(srv["port"] for srv in SERVER_DATA if srv["name"] == server.name))

    server_players = gs.a2s_players((ip, port))

    player_table = []
    for player in server_players:
        if player["name"]:
            player_table.append([player["name"], format_time(player["duration"])])

    formated_message = format_message(player_table, server.name)

    await interaction.response.send_message(formated_message)
