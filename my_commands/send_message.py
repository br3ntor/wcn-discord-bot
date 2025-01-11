import discord
from discord import app_commands

from config import Config
from lib.pzserver import pz_send_message
from lib.server_utils import server_isrunning

SERVER_NAMES = Config.SERVER_NAMES
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES)
    ]
)
@app_commands.describe(
    server="Which server should recieve this message?",
    message="What would you like to say?",
)
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def send_message(
    interaction: discord.Interaction, server: app_commands.Choice[int], message: str
):
    """Send a message to everyone in the server."""
    await interaction.response.defer()

    system_user = SERVER_NAMES[server.name]

    # Check if game server is running before we send any commands
    is_running = await server_isrunning(system_user)
    if not is_running:
        await interaction.followup.send(f"{server.name} is **NOT** running!")
        return

    result = await pz_send_message(system_user, message)

    status = (
        f"Message sent to **{server.name}** server:\n> {message}"
        if result
        else "Something wrong maybe, check logs!"
    )

    await interaction.followup.send(status)
