import discord
from discord import app_commands
from utils.db_helpers import user_exists
import asyncio

ban_group = app_commands.Group(
    name="ban", description="Ban, unban, and list banned players."
)


@ban_group.command(name="player")
@app_commands.choices(
    server=[
        app_commands.Choice(name="Light", value=1),
        app_commands.Choice(name="Heavy", value=2),
    ],
)
@app_commands.describe(
    server="Which server?",
    player="Which player?",
)
async def ban_player(
    interaction: discord.Interaction, server: app_commands.Choice[int], player: str
):
    player_exists = await user_exists(server.name.lower(), player)
    msg = (
        f"The player {player} was found, should we ban them?"
        if player_exists
        else f"The player {player} was NOT found."
    )
    await interaction.response.send_message(msg)
