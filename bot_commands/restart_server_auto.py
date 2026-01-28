import discord
from discord import app_commands

from config import Config
from lib.countdown import abort_signal, countdown_isrunning
from lib.discord_utils import auto_restart_server

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID


class Confirm(discord.ui.View):
    def __init__(self, server: str):
        super().__init__()
        self.value = None
        self.server = server

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "Auto Restart Confirmed.", ephemeral=True
        )
        self.value = True
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Auto Restart Aborted.", ephemeral=True)
        self.value = False
        self.stop()


@app_commands.command(name="auto")
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES.values())
    ]
)
@app_commands.describe(server="Which server?")
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def restart_server_auto(
    interaction: discord.Interaction, server: app_commands.Choice[int]
):
    """Restarts server in 5min."""

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

        # Not sure if I should raise for these or not...
        if not isinstance(interaction.guild, discord.Guild):
            raise TypeError("Not a guild")
        announce_chan = interaction.guild.get_channel(ANNOUNCE_CHANNEL)
        if not isinstance(announce_chan, discord.TextChannel):
            raise TypeError("Not a text channel")

        await auto_restart_server(announce_chan, server.name, init_msg)

    else:
        print(f"Restart cancelled for {server.name}...")


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
