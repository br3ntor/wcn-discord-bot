import os
import discord
from discord import app_commands
from steam import game_servers as gs
from tabulate import tabulate
import time

VANILLA_SERVER = os.getenv("VANILLA_SERVER")
MODDED_SERVERS = os.getenv("MODDED_SERVERS")


def format_time(seconds):
    time_str = time.strftime("%Hhr %Mmin", time.gmtime(seconds))
    return time_str


def format_message(player_table, server_name):
    msg = f"""```md
I can see {len(player_table)} players on the {server_name} server.

{tabulate(player_table, headers=["Name", "Duration"])}
    ```"""
    return msg


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name="Vanilla", value=1),
        app_commands.Choice(name="Light", value=2),
        app_commands.Choice(name="Heavy", value=3),
    ]
)
async def get_playerlist(
    interaction: discord.Interaction, server: app_commands.Choice[int]
):
    """Get a list of players on the server."""
    servers = {
        "vanilla": (VANILLA_SERVER, 16261),
        "light": (MODDED_SERVERS, 16261),
        "heavy": (MODDED_SERVERS, 27901),
    }

    server_players = gs.a2s_players(servers[server.name.lower()])

    player_table = []
    for player in server_players:
        if player["name"]:
            player_table.append([player["name"], format_time(player["duration"])])

    formated_message = format_message(player_table, server.name)

    await interaction.response.send_message(formated_message)
