import logging

import discord
from discord import app_commands

from src.config import Config
from src.services.chat_transcript import build_general_transcript
from src.services.llm import summarize_chat

logger = logging.getLogger(__name__)

SYSTEM_USERS = Config.SYSTEM_USERS
PZ_ADMIN_ROLE_ID = Config.PZ_ADMIN_ROLE_ID
DEFAULT_HOURS = 12
MAX_EMBED_DESCRIPTION = 4000


@app_commands.command(
    name="chat_summary",
    description="AI summary of in-game global chat for a server.",
)
@app_commands.choices(
    server=[
        app_commands.Choice(name=srv, value=index + 1)
        for index, srv in enumerate(SYSTEM_USERS.keys())
    ],
)
@app_commands.describe(server="Which server?", hours="How far back to summarize")
@app_commands.checks.has_role(PZ_ADMIN_ROLE_ID)
async def chat_summary(
    interaction: discord.Interaction,
    server: app_commands.Choice[int],
    hours: app_commands.Range[int, 1, 48] = DEFAULT_HOURS,
):
    """Summarize global chat for a server using AI."""
    await interaction.response.defer()
    system_user = SYSTEM_USERS[server.name]

    try:
        transcript = await build_general_transcript(system_user, hours)
        if not transcript:
            await interaction.followup.send(
                f"No global chat found on **{server.name}** in the last {hours}h."
            )
            return

        summary = await summarize_chat(transcript, server.name, hours)
        if not summary:
            await interaction.followup.send(
                "The AI returned an empty summary, try again."
            )
            return

        embed = discord.Embed(
            title=f"{server.name} — chat summary (last {hours}h)",
            description=summary[:MAX_EMBED_DESCRIPTION],
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        await interaction.followup.send(embed=embed)
    except Exception:
        logger.exception("chat_summary failed for %s", server.name)
        await interaction.followup.send(
            "An error occurred while generating the summary, check logs."
        )
