import discord
from commands import test


def load_commands(client):
    @client.tree.command()
    async def hello(interaction: discord.Interaction):
        """Say hello."""
        await test(interaction)
