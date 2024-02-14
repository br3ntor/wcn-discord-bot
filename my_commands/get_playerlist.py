import os
import discord
from discord import app_commands
from steam import game_servers as gs
from tabulate import tabulate
import time

SERVER_IP = os.getenv("SERVER_IP")


def format_time(seconds: float) -> str:
    time_str = time.strftime("%Hhr %Mmin", time.gmtime(seconds))
    return time_str


def format_message(player_table: list, server_name: str) -> str:
    msg = f"""```md
I can see {len(player_table)} players on the {server_name} server.

{tabulate(player_table, headers=["Name", "Duration"])}
    ```"""
    return msg


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name="Vanilla", value=1),
        app_commands.Choice(name="Modded", value=2),
    ]
)
async def get_playerlist(
    interaction: discord.Interaction, server: app_commands.Choice[int]
):
    """Get a list of players on the server."""

    servers = {
        "vanilla": (SERVER_IP, 27901),
        "modded": (SERVER_IP, 16261),
    }

    server_players = gs.a2s_players(servers[server.name.lower()])

    player_table = []
    for player in server_players:
        if player["name"]:
            player_table.append([player["name"], format_time(player["duration"])])

    formated_message = format_message(player_table, server.name)

    await interaction.response.send_message(formated_message)
