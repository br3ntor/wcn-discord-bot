import discord
from discord import app_commands

from src.config import Config
from src.features.skill_restore import LevelRestore

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
@app_commands.describe(
    server="Which server?", player="Player name to restore levels for"
)
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def restore_levels(
    interaction: discord.Interaction, server: app_commands.Choice[int], player: str
):
    """Restores a player's skill levels to what they were before their most significant death."""
    await interaction.response.defer()

    lr = LevelRestore(server.name, player)
    result = await lr.restore_levels()

    if result:
        await interaction.followup.send(
            f"Successfully restored skill levels for **{player}** on the **{server.name}** server! 🔄"
        )
    else:
        await interaction.followup.send(
            f"Level restore failed for **{player}** on the **{server.name}** server. "
            f"Player must be online, not have admin privileges, have a death record in the logs, "
            f"and be findable in the database/logs. See console logs for details."
        )
