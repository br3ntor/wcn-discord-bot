import discord
from discord import app_commands
import asyncio


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name="Light", value=1),
        app_commands.Choice(name="Heavy", value=2),
    ],
    accesslevel=[
        app_commands.Choice(name="Give admin", value=1),
        app_commands.Choice(name="Remove admin", value=2),
    ],
)
@app_commands.describe(
    server="Which server to send command.",
    accesslevel="The choice to give or take admin",
    player="The name of the player in game.",
)
async def admin(
    interaction: discord.Interaction,
    server: app_commands.Choice[int],
    accesslevel: app_commands.Choice[int],
    player: str,
):
    """Add or remove admin acccesslevel from player."""
    await interaction.response.defer()

    access_level = "admin" if accesslevel.value == 1 else "none"
    server_msg = f"'setaccesslevel {player} {access_level}'"

    destination_server = server.name.lower()
    cmd = [
        "runuser",
        f"pzserver{destination_server}",
        "-c",
        f"/home/pzserver{destination_server}/pzserver send {server_msg}",
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )

        # Get the output of the subprocess.
        output, error = await process.communicate()

    except asyncio.SubprocessError as e:
        print(f"Subprocess error occurred: {e}")

    print(output.decode())
    print(error.decode())

    emoji = "🥗" if destination_server == "light" else "🍖"
    status = (
        f"{player} accesslevel has been set to {access_level} on the {emoji}{destination_server} server"
        if "OK" in output.decode()
        else "Something wrong maybe\n" + output.decode()
    )

    await interaction.followup.send(status)
