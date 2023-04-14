import discord
from discord import app_commands
import aiohttp


async def get_cat_fact():
    url = "https://catfact.ninja/fact"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            fact = await response.json()
            return fact["fact"]


@app_commands.command()
async def cat_fact(interaction: discord.Interaction):
    """Get a random cat fact."""
    fact = await get_cat_fact()
    await interaction.response.send_message(fact)
