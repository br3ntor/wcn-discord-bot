import os
import re
import asyncio
import discord
from discord import app_commands

MOD_ROLE_ID = int(os.getenv("MOD_ROLE_ID"))


@app_commands.command()
@app_commands.describe(
    message="What would you like to say?",
)
async def send_message(interaction: discord.Interaction, message: str):
    """Send a message to everyone in the server."""

    # Only discord mods can use the command
    # This gets taken care of when setuping up bot but its nice to have still
    # Oh also the framwork has a special check function to do this already I should use
    if interaction.user.get_role(MOD_ROLE_ID) is None:
        await interaction.response.send_message("You are not worthy.", ephemeral=True)
        return

    # This def needs to be called before doing work that takes time,
    # but I wonder if it may as well be first line of the function?
    await interaction.response.defer()

    # Send command and respond to result
    valid_msg = re.sub(r"[^a-zA-Z!?\s\d]", "", message)
    server_msg = f'servermsg "{valid_msg}"'
    cmd = ["/home/pzserver/pzserver", "send", server_msg]

    process = await asyncio.create_subprocess_exec(
        *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
    )

    # Get the output of the subprocess.
    output, error = await process.communicate()

    # I don't think this is needed but doesn't hurt either
    await process.wait()

    print(output.decode())
    print(error.decode())

    status = (
        f"Message sent to server:\n> {message}"
        if "OK" in output.decode()
        else "Something wrong maybe\n" + output.decode()
    )

    await interaction.followup.send(status)
