import os
import time

import discord
from discord import app_commands
from steam import game_servers as gs
from tabulate import tabulate

SERVER_IP = os.getenv("SERVER_IP")


def format_time(seconds: float) -> str:
    time_str = time.strftime("%Hhr %Mmin", time.gmtime(seconds))
    return time_str


def format_message(player_table: list) -> str:
    msg = f"""```md
I can see {len(player_table)} players on the server.

{tabulate(player_table, headers=["Name", "Duration"])}
    ```"""
    return msg


@app_commands.command()
async def get_playerlist(interaction: discord.Interaction):
    """Get a list of players on the server."""

    server_players = gs.a2s_players((SERVER_IP, 16261))

    player_table = []
    for player in server_players:
        if player["name"]:
            player_table.append([player["name"], format_time(player["duration"])])

    formated_message = format_message(player_table)

    await interaction.response.send_message(formated_message)
