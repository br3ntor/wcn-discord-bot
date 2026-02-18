import discord
from discord import app_commands

from src.config import Config
from src.features.godmode import GodMode

SYSTEM_USERS = Config.SYSTEM_USERS
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID
SERVER_NAMES = Config.SERVER_NAMES


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES.values())
    ]
)
@app_commands.describe(server="Which server?", player="Who will you save?")
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def heal_player(
    interaction: discord.Interaction, server: app_commands.Choice[int], player: str
):
    """Heals a player by toggling godmode on and off."""
    await interaction.response.defer()
    gm = GodMode(server.name, player)
    result = await gm.gogo_godmode()
    if result:
        await interaction.followup.send(
            f"I have healed 💖 **{player}** on the **{server.name}** server!"
        )
    else:
        await interaction.followup.send(
            f"Heal failed, **{player}** must be on the **{server.name}** server and must not be admin, gm, etc. See logs."
        )
