import asyncio

import discord
from discord import app_commands

from config import Config
from discord_utils.auto_restart import abort_signal, countdown_isrunning
from lib.pzserver import pz_send_message
from lib.server_utils import server_isrunning

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
SERVER_NAMES = Config.SERVER_NAMES
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID


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


@app_commands.command(name="auto")
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES)
    ]
)
@app_commands.describe(server="Which server?")
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def restart_server_auto(
    interaction: discord.Interaction, server: app_commands.Choice[int]
):
    """Restarts server in 5min."""
    if countdown_isrunning[server.name]:
        await interaction.response.send_message(
            f"Auto restart already started for **{server.name}**."
        )
        return

    if abort_signal["aborted"]:
        await interaction.response.send_message(
            "Try again after last auto_restart finishes canceling"
        )
        return
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "WTF are you trying to do even?", ephemeral=True
        )
        raise TypeError("Not a member")

    if not isinstance(interaction.guild, discord.Guild):
        raise TypeError("Not a guild")

    if not isinstance(interaction.channel, discord.TextChannel):
        raise TypeError("Not a text channel")

    announce_chan = interaction.guild.get_channel(ANNOUNCE_CHANNEL)
    if not isinstance(announce_chan, discord.TextChannel):
        raise TypeError("Not a text channel")

    system_user = SERVER_NAMES[server.name]

    is_running = await server_isrunning(system_user)
    if not is_running:
        await interaction.response.send_message(
            f"**{server.name}** is **NOT** running!"
        )
        return

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
        print("Auto Restart Confirmed...")

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
            if abort_signal["aborted"]:
                countdown_isrunning[server.name] = False
                await interaction.channel.send(
                    f"Auto restart ABORTED 👼 for the **{server.name}** server."
                )
                await announce_chan.send(
                    f"Auto restart ABORTED 👼 for the **{server.name}** server."
                )
                await pz_send_message(
                    SERVER_NAMES[server.name], "Restart has been ABORTED"
                )
                abort_signal["aborted"] = False
                return

            # Here we send restart msg to game server every minute
            if seconds_left % 60 == 0:
                await pz_send_message(
                    system_user,
                    f"The server will restart in {seconds_left//60} minute(s)!",
                )

            # Last minute we send msg to mods to give them last chance to abort
            if seconds_left == 60:
                await interaction.channel.send(
                    f"The **{server.name}** server will restart in 1 minute!"
                )

            await asyncio.sleep(5)
            seconds_left -= 5

        try:
            cmd = [
                "sudo",
                "/usr/bin/systemctl",
                "restart",
                system_user,
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

        # Might as well be here right? So
        # command cant be called twice for as long as it is running.
        countdown_isrunning[server.name] = False

    else:
        print("Cancelled...")


@app_commands.command(name="cancel")
async def cancel_restart(interaction: discord.Interaction):
    """Cancels all running restart countdowns."""
    if abort_signal["aborted"]:
        await interaction.response.send_message("You already cancelled let it finish!")
        return

    is_running = any(countdown_isrunning.values())

    if is_running:
        abort_signal["aborted"] = True
        await interaction.response.send_message("Abort signal sent!")
    else:
        await interaction.response.send_message(
            "There are no countdown happening, this is you 🤡"
        )
