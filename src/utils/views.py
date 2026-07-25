import discord


class Confirm(discord.ui.View):
    """A simple confirmation dialog with Yes/No buttons."""

    def __init__(
        self,
        confirm_msg: str = "Confirmed.",
        cancel_msg: str = "Canceled.",
    ):
        super().__init__()
        self.value = None
        self._confirm_msg = confirm_msg
        self._cancel_msg = cancel_msg

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message(self._confirm_msg, ephemeral=True)
        self.value = True
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(self._cancel_msg, ephemeral=True)
        self.value = False
        self.stop()
