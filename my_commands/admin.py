import discord
from discord import app_commands
import asyncio
import aiosqlite
import re
from utils.db_helpers import get_user, get_admins

admin_group = app_commands.Group(
    name="admin", description="Commands to control in-game accesslevel."
)


@admin_group.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name="Vanilla", value=1),
        app_commands.Choice(name="Modded", value=2),
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
async def toggle(
    interaction: discord.Interaction,
    server: app_commands.Choice[int],
    accesslevel: app_commands.Choice[int],
    player: str,
):
    """Give or remove admin powers."""
    if re.search(r"[\"']", player):
        await interaction.response.send_message("Quotes not allowed.")
        return

    # Should be called before the first db call
    await interaction.response.defer()

    destination_server = "vanilla_pz" if server.value == 1 else "pzserver"

    if not await get_user(destination_server, player):
        await interaction.followup.send(f"username: {player} not found in database")
        return

    access_level = "admin" if accesslevel.value == 1 else "none"
    server_msg = f'setaccesslevel "{player}" {access_level}'

    cmd = [
        "runuser",
        f"{destination_server}",
        "-c",
        f"/home/{destination_server}/pzserver send '{server_msg}'",
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

    emoji = "🥛" if destination_server == "vanilla_pz" else "🍖"
    status = (
        f"{player} accesslevel has been set to **{access_level}** "
        f"on the {emoji} **{server.name}** zomboid server"
        if "OK" in output.decode()
        else "Something wrong maybe\n" + output.decode()
    )

    await interaction.followup.send(status)


@admin_group.command()
async def list(interaction: discord.Interaction):
    """Get a list of admins on zomboid server."""
    the_boys_vanilla = await get_admins("vanilla_pz")
    the_boys_modded = await get_admins("pzserver")
    await interaction.response.send_message(
        "**Vanilla admins**:\n"
        f"{the_boys_vanilla}\n"
        "**Modded admins**:\n"
        f"{the_boys_modded}\n"
    )


async def get_admins(server: str) -> str:
    async with aiosqlite.connect(f"/home/{server}/Zomboid/db/pzserver.db") as db:
        async with db.execute(
            "SELECT username FROM whitelist WHERE accesslevel='admin'"
        ) as cursor:
            the_boys = []
            async for row in cursor:
                the_boys.append(row[0])
            return ", ".join(sorted(the_boys, key=str.casefold))
