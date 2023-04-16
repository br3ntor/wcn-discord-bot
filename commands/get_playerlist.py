import os
import discord
from discord import app_commands
from steam import game_servers as gs

VANILLA_SERVER = os.getenv("VANILLA_SERVER")
MODDED_SERVERS = os.getenv("MODDED_SERVERS")


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
    players = [p["name"] for p in server_players if p["name"]]
    list_message = ", ".join(players) if players else "No body on :("
    print(list_message)
    await interaction.response.send_message(
        f"{server.name} players online: {list_message}"
    )
