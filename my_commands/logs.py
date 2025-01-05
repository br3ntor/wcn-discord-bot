import asyncio
import os
import shlex
from datetime import datetime

import discord
from discord import app_commands

from config import SERVER_NAMES
from utils.db_helpers import get_user

logs_group = app_commands.Group(
    name="logs", description="get_player_logs, and get_all_logs commands."
)

# TODO: Maybe checkout the tempfile built-in python module sometime, safer, more robust etc
# https://docs.python.org/3/library/tempfile.html#examples


@logs_group.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES)
    ],
)
@app_commands.describe(server="Which server?", playername="Which player?")
async def get_player_logs(
    interaction: discord.Interaction, server: app_commands.Choice[int], playername: str
):
    """Get all logs for a player since last server restart."""
    await interaction.response.defer()

    try:
        # Check if player exists in db, then get all them logs
        player = await get_user(server.name, playername)
        if not player:
            await interaction.followup.send(
                f"**{playername}** was not found in the database for **{server.name}**."
            )
            return

        current_date = datetime.now().strftime("%Y-%m-%d")
        output_file = f"/tmp/{playername}_{server.name}_{current_date}.txt"
        logs_dir = f"/home/{server.name}/Zomboid/Logs"

        # Sanitize inputs
        safe_playername = shlex.quote(playername)
        safe_output_file = shlex.quote(output_file)

        # Execute grep command asynchronously
        process = await asyncio.create_subprocess_shell(
            f"cd {logs_dir};grep {safe_playername} *.txt > {safe_output_file}",
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
                f"Logs for user {playername} on {server.name}:",
                file=discord.File(output_file),
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


@logs_group.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES)
    ],
    days=[
        app_commands.Choice(name=day, value=index + 1)
        for index, day in enumerate(["one", "two", "three"])
    ],
)
@app_commands.describe(
    server="Which server?",
    days="From how many days ago...",
)
async def get_all_logs(
    interaction: discord.Interaction,
    server: app_commands.Choice[int],
    days: app_commands.Choice[int],
):
    """Get all logs from date range."""
    await interaction.response.defer()

    current_date = datetime.now().strftime("%Y-%m-%d")
    output_file = f"/tmp/{server.name}_{current_date}_plus_{days.name}_days.zip"
    logs_dir = f"/home/{server.name}/Zomboid/Logs"

    # Sanitize inputs (i dont think we need this since thers no direct player input)
    # safe_output_file = shlex.quote(output_file)
    # safe_logs_dir = shlex.quote(logs_dir)

    try:

        # Execute grep command asynchronously
        process = await asyncio.create_subprocess_shell(
            f"cd {logs_dir};zip -r {output_file} *.txt $(find . -mindepth 1 -type d -mtime -{days.value})",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await process.communicate()

        # Check if command succeeded and file exists with content
        if (
            process.returncode == 0
            and os.path.exists(output_file)
            and os.path.getsize(output_file) > 0
        ):
            print(f"Created zip of log files: {output_file}")
            await interaction.followup.send(
                f"Logs for {server.name}:", file=discord.File(output_file)
            )
        else:
            error_msg = stderr.decode() if stderr else "No logs files?"
            await interaction.followup.send(f"No logs found . {error_msg}")

        # Clean up
        if os.path.exists(output_file):
            os.remove(output_file)

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}")
