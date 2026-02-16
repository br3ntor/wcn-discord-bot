import aiohttp
import discord
from discord import app_commands


@app_commands.command()
async def cat_fact(interaction: discord.Interaction):
    """Get a random cat fact."""
    url = "https://catfact.ninja/fact"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            fact = await response.json()
            await interaction.response.send_message(fact["fact"], tts=True)
