import asyncio
import os
import shlex
from datetime import datetime

import discord
from discord import app_commands

from config import LOCAL_SERVER_NAMES
from utils.db_helpers import get_user


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(LOCAL_SERVER_NAMES)
    ],
)
@app_commands.describe(server="Which server?", playername="Which player?")
async def get_player_logs(
    interaction: discord.Interaction, server: app_commands.Choice[int], playername: str
):
    """Get all logs for a player."""
    # await interaction.response.defer(ephemeral=True)
    await interaction.response.defer()

    try:
        # Check if player exists in db, then get all them logs
        player = await get_user(server.name, playername)
        if not player:
            await interaction.response.send_message(
                f"**{playername}** was not found in the database for **{server}**."
            )
            return

        current_date = datetime.now().strftime("%Y-%m-%d")
        output_file = f"./{playername}_{current_date}.txt"

        # Sanitize inputs
        safe_playername = shlex.quote(playername)
        safe_output_file = shlex.quote(output_file)

        # Execute grep command asynchronously
        process = await asyncio.create_subprocess_shell(
            f"grep {safe_playername} /home/{server.name}/Zomboid/Logs/*.txt > {safe_output_file}",
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await process.communicate()

        # Check if command succeeded and file exists with content
        if (
            process.returncode == 0
            and os.path.exists(output_file)
            and os.path.getsize(output_file) > 0
        ):
            print(f"Created playerlogs file: {output_file}")
            await interaction.followup.send(
                f"Logs for user {playername}:", file=discord.File(output_file)
            )
        else:
            error_msg = stderr.decode() if stderr else "No logs found"
            await interaction.followup.send(
                f"No logs found for user {playername}. {error_msg}"
            )

        # Clean up
        if os.path.exists(output_file):
            os.remove(output_file)

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}")
