"""Discord UI views for ban commands."""

import discord
from tabulate import tabulate

from src.services.pocketbase import pb_client


class BanListView(discord.ui.View):
    """View for paginated ban list display."""

    def __init__(self, page: int, total_pages: int, total_items: int):
        super().__init__(timeout=120)
        self.page = page
        self.total_pages = total_pages
        self.total_items = total_items

        self.previous_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.total_pages

    def build_embed(self, bans: list) -> discord.Embed:
        embed = discord.Embed(title="Global Ban List", color=discord.Color.red())

        table_rows = [
            {
                "name": b.get("name", "Unknown"),
                "steamid": b.get("steamid"),
                "expires": b.get("expires") or "Permanent",
                "is_active": "Active" if b.get("is_active", False) else "Inactive",
            }
            for b in bans
        ]

        if table_rows:
            ban_table = tabulate(table_rows, headers="keys")
            embed.description = f"```\n{ban_table}\n```"

        embed.set_footer(
            text=f"Page {self.page} of {self.total_pages} • {self.total_items} total bans"
        )
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page -= 1
        result = await pb_client.get_bans_paginated(self.page, 25)

        self.previous_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.total_pages

        await interaction.response.edit_message(
            embed=self.build_embed(result.get("items", [])), view=self
        )

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page += 1
        result = await pb_client.get_bans_paginated(self.page, 25)

        self.previous_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.total_pages

        await interaction.response.edit_message(
            embed=self.build_embed(result.get("items", [])), view=self
        )
