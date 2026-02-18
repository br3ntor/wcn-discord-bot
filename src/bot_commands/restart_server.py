import discord
from discord import app_commands

from src.config import Config
from src.services.server import restart_zomboid_server, server_isrunning

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID


# Define a simple View that gives us a confirmation menu
class Confirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message("Restart confirmed.", ephemeral=True)
        self.value = True
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Restart canceled.", ephemeral=True)
        self.value = False
        self.stop()


@app_commands.command(name="now")
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SERVER_NAMES.values())
    ]
)
@app_commands.describe(server="Which server?")
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def restart_server(
    interaction: discord.Interaction, server: app_commands.Choice[int]
):
    """Restarts a server immediately."""

    # Send the question with buttons
    view = Confirm()
    await interaction.response.send_message(
        f"Restart the **{server.name}** server?", view=view, ephemeral=True
    )
    await view.wait()

    # Disable buttons after click
    for button in view.children:
        if isinstance(button, discord.ui.Button):
            button.disabled = True
    await interaction.edit_original_response(view=view)

    # Action taken based on interaction results
    if view.value is None:
        print("Timed out...")
    elif view.value:
        print("Restart Confirmed...")

        system_user = SYSTEM_USERS[server.name]

        is_running = await server_isrunning(system_user)
        if not is_running:
            await interaction.followup.send(
                f"**{server.name}** is **NOT** running!", ephemeral=True
            )
            return

        initiated_by = (
            f"**{server.name}** server restart "
            f"initiated by {interaction.user.display_name}..."
        )

        if interaction.guild is None:
            await interaction.followup.send(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        announce_chan = interaction.guild.get_channel(ANNOUNCE_CHANNEL)

        if not isinstance(announce_chan, discord.TextChannel):
            await interaction.followup.send(
                "Announce channel is not a TextChanel.", ephemeral=True
            )
            return

        # Let the people know whats up!
        await announce_chan.send(initiated_by)

        await restart_zomboid_server(system_user)

        status_msg = (
            f"Success! The **{server.name}** was shut down "
            "and is now starting back up."
        )

        # Announce restart
        await announce_chan.send(status_msg)

    else:
        print(f"Restart cancelled for {server.name}...")
