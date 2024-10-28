import asyncio
import os

import discord
from discord import app_commands

from config import LOCAL_SERVER_NAMES
from utils.server_helpers import server_isrunning

MOD_ROLE_ID = int(os.getenv("MOD_ROLE_ID", 0))
ANNOUNCE_CHANNEL = int(os.getenv("ANNOUNCE_CHANNEL", 0))


# Track if countdown timer is running
countdown_isrunning = {server: False for server in LOCAL_SERVER_NAMES}

# Will abort all running countdowns
abort_signal = False


async def send_server_msg(server: str, message: str):
    server_msg = f'servermsg "{message}"'
    cmd = [
        "runuser",
        f"{server}",
        "-c",
        f"/home/{server}/pzserver send '{server_msg}'",
    ]
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )
        # Get the output of the subprocess.
        output, error = await process.communicate()
    except Exception as e:
        print("Error in try block:", e)

    print(output.decode())
    print(error.decode())


class Confirm(discord.ui.View):
    def __init__(self, server: str):
        super().__init__()
        self.value = None
        self.server = server

    # When the confirm button is pressed, set the inner value to `True` and
    # stop the View from listening to more input.
    # We also send the user an ephemeral message that we're confirming their choice.
    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "Auto Restart Confirmed.", ephemeral=True
        )
        # I guess interaction.channel can be diff types of channel not all having send methods
        # So this checks for that although I dont think it ever would not be but I like to may pyright happy
        # Besides I always am learning stuff when its upset
        if isinstance(interaction.channel, discord.TextChannel):
            await interaction.channel.send(
                f"{interaction.user.display_name} has initiated the **{self.server}** auto restart. Restarting in 5min."
            )
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except
    # sets the inner value to `False`
    @discord.ui.button(label="No", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Auto Restart Aborted.", ephemeral=True)
        self.value = False
        self.stop()


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(LOCAL_SERVER_NAMES)
    ]
)
@app_commands.describe(server="Which server?")
async def restart_server_auto(
    interaction: discord.Interaction, server: app_commands.Choice[int]
):
    """Restarts server in 5min."""
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "WTF are you trying to do even?", ephemeral=True
        )
        raise TypeError("Not a member")

    # NOTE: I've decided to use just the server settings to check permissions for now
    # Only discord mods can use the command there might be built in check for this, check docs
    # if interaction.user.get_role(MOD_ROLE_ID) is None:
    #     await interaction.response.send_message("You are not worthy.", ephemeral=True)
    #     return

    if not isinstance(interaction.guild, discord.Guild):
        raise TypeError("Not a guild")

    if not isinstance(interaction.channel, discord.TextChannel):
        raise TypeError("Not a text channel")

    announce_chan = interaction.guild.get_channel(ANNOUNCE_CHANNEL)
    if not isinstance(announce_chan, discord.TextChannel):
        raise TypeError("Not a text channel")

    is_running = await server_isrunning(server.name)
    if not is_running:
        await interaction.response.send_message(
            f"**{server.name}** is **NOT** running!"
        )
        return

    global abort_signal, countdown_isrunning
    abort_signal = False

    # Create the view containing our dropdown and buttons
    view = Confirm(server.name)
    await interaction.response.send_message(
        f"Automatically restart the **{server.name}** after 5min?",
        view=view,
        ephemeral=True,
    )
    await view.wait()

    # Disable all elements after button is pressed
    for element in view.children:
        if isinstance(element, discord.ui.Button):
            element.disabled = True
        else:
            raise TypeError(f"Unexpected item type: {type(element)}")

    await interaction.edit_original_response(view=view)

    if view.value is None:
        print("Timed out...")
    elif view.value:
        print("Confirmed...")

        init_msg = (
            f"{interaction.user.display_name} has initiated the **{server.name}** auto restart. "
            f"Restarting in 5min."
        )
        # Send message to discord members announcing restart
        await announce_chan.send(init_msg)

        # Start tracking running countdowns
        countdown_isrunning[server.name] = True
        seconds_left = 300
        while seconds_left > 0:
            if abort_signal:
                countdown_isrunning[server.name] = False
                await interaction.channel.send(
                    f"Auto restart ABORTED 👼 for the **{server.name}** server."
                )
                await announce_chan.send(
                    f"Auto restart ABORTED 👼 for the **{server.name}** server."
                )
                await send_server_msg(server.name, "Restart has been ABORTED")
                return

            # Here we send restart msg to game server every minute
            if seconds_left % 60 == 0:
                await send_server_msg(
                    server.name,
                    f"The server will restart in {seconds_left//60} minute(s)!",
                )

            # Last minute we send msg to mods to give them last chance to abort
            if seconds_left == 60:
                await interaction.channel.send(
                    f"The **{server.name}** server will restart in 1 minute!"
                )

            await asyncio.sleep(5)
            seconds_left -= 5

        # Countdown is over so lets reset count_down trackers
        countdown_isrunning[server.name] = False

        try:
            cmd = [
                "systemctl",
                "restart",
                server.name,
            ]
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.wait()

        except Exception as e:
            print(f"error occurred: {e}")

        restart_msg = (
            f"Success! The **{server.name}** "
            "was restarted and is now loading back up."
        )
        await interaction.channel.send(restart_msg)
        await announce_chan.send(restart_msg)

    else:
        print("Cancelled...")


@app_commands.command()
async def cancel_auto_restart(interaction: discord.Interaction):
    """ZOMG CANCEL B4 IT TOO LATE!!!."""
    global abort_signal

    is_running = any(countdown_isrunning.values())

    if is_running:
        abort_signal = True
        await interaction.response.send_message("Abort signal sent!")
    else:
        await interaction.response.send_message(
            "There are no countdown happening, this is you 🤡"
        )
