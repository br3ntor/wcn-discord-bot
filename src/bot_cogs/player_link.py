import asyncio
import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from src.config import Config
from src.services.bot_db import (
    cleanup_pending_player_links,
    consume_pending_player_link,
    create_pending_player_link,
    get_active_pending_link_servers,
    get_pending_player_link,
    invalidate_pending_player_links,
)
from src.services.log_watcher import RealTimeLogProcessor
from src.services.pocketbase import pb_client
from src.services.server import get_zomboid_logs_dir
from src.utils.player_lookup import lookup_player

logger = logging.getLogger(__name__)

LINK_EXPIRY = timedelta(minutes=10)
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
VERIFY_PATTERN = re.compile(r"^!verify\s+([A-Z0-9]{8})$", re.IGNORECASE)
CHAT_PATTERN = re.compile(
    r"Got message:ChatMessage\{chat=([^,]+), author='([^']*)', text='(.*?)'\}\."
)

SERVER_CHOICES = [
    app_commands.Choice(name=server["server_name"], value=server["server_name"])
    for server in Config.SERVER_DATA
]


def parse_local_verification_message(line: str) -> tuple[str, str] | None:
    """Parse a local chat message from a Zomboid chat log line."""
    match = CHAT_PATTERN.search(line)
    if not match or match.group(1) != "Local":
        return None

    return match.group(2), match.group(3)


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.upper().encode("ascii")).hexdigest()


def _generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


class PlayerLinkCog(commands.Cog):
    """Links Discord accounts to Project Zomboid Steam IDs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.verification_watchers: dict[str, RealTimeLogProcessor] = {}
        self.watcher_cleanup_tasks: dict[str, asyncio.Task] = {}

    async def cog_load(self):
        await cleanup_pending_player_links()
        for server_name in await get_active_pending_link_servers():
            await self._ensure_verification_watcher(server_name)

    async def cog_unload(self):
        cleanup_tasks = list(self.watcher_cleanup_tasks.values())
        for task in cleanup_tasks:
            task.cancel()
        for task in cleanup_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass

        monitors = list(self.verification_watchers.values())
        for monitor in monitors:
            await monitor.stop()

        self.watcher_cleanup_tasks.clear()
        self.verification_watchers.clear()

    @app_commands.command(name="link", description="Link your Discord account to your in-game player.")
    @app_commands.choices(server=SERVER_CHOICES)
    @app_commands.describe(server="The server where you will enter the verification code")
    async def link(self, interaction: discord.Interaction, server: app_commands.Choice[str]):
        """Create a temporary code for linking a Discord account to a player."""
        await interaction.response.defer(ephemeral=True)

        if not await pb_client.ensure_authenticated():
            await interaction.followup.send(
                "Player linking is temporarily unavailable because the central database could not be reached."
            )
            return

        code = _generate_code()
        expires_at = datetime.now(timezone.utc) + LINK_EXPIRY
        discord_id = str(interaction.user.id)

        try:
            await interaction.user.send(
                f"Your Project Zomboid link code is `{code}`.\n"
                f"Enter `!verify {code}` in **local chat** on the **{server.name}** server "
                "within 10 minutes."
            )
        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send(
                "I could not DM you. Please enable direct messages from this server and try again."
            )
            return

        await invalidate_pending_player_links(discord_id)
        stored = await create_pending_player_link(
            discord_id=discord_id,
            server_name=server.name,
            code_hash=_hash_code(code),
            expires_at=expires_at,
        )
        if not stored:
            await interaction.followup.send(
                "I could not save your pending link request. Please try again."
            )
            return

        await self._ensure_verification_watcher(server.name)
        await interaction.followup.send(
            f"I sent your code by DM. Enter it in local chat on **{server.name}** within 10 minutes."
        )

    async def _ensure_verification_watcher(self, server_name: str):
        existing = self.verification_watchers.get(server_name)
        if existing and existing.watch_task and not existing.watch_task.done():
            return

        server_config = Config.get_rcon_config(server_name)
        if not server_config:
            logger.error("Cannot start link watcher: unknown server %s", server_name)
            return

        system_user = server_config["system_user"]

        async def callback(line: str):
            await self._handle_chat_line(server_name, system_user, line)

        monitor = RealTimeLogProcessor(
            str(get_zomboid_logs_dir(system_user)),
            "*chat.txt",
            callback,
            start_at_end=True,
        )
        self.verification_watchers[server_name] = monitor
        monitor.start()
        logger.info("Started temporary player-link watcher for %s", server_name)

        old_cleanup = self.watcher_cleanup_tasks.get(server_name)
        if old_cleanup:
            old_cleanup.cancel()
        self.watcher_cleanup_tasks[server_name] = asyncio.create_task(
            self._stop_watcher_when_idle(server_name, monitor)
        )

    async def _stop_watcher_when_idle(
        self, server_name: str, monitor: RealTimeLogProcessor
    ):
        try:
            while True:
                await asyncio.sleep(5)
                active_servers = await get_active_pending_link_servers()
                if server_name not in active_servers:
                    await monitor.stop()
                    if self.verification_watchers.get(server_name) is monitor:
                        self.verification_watchers.pop(server_name, None)
                    logger.info("Stopped temporary player-link watcher for %s", server_name)
                    return
        except asyncio.CancelledError:
            raise
        finally:
            current_task = asyncio.current_task()
            if self.watcher_cleanup_tasks.get(server_name) is current_task:
                self.watcher_cleanup_tasks.pop(server_name, None)

    async def _handle_chat_line(
        self, server_name: str, system_user: str, line: str
    ):
        parsed = parse_local_verification_message(line)
        if not parsed:
            return

        author, text = parsed
        verify_match = VERIFY_PATTERN.fullmatch(text.strip())
        if not verify_match:
            return

        code_hash = _hash_code(verify_match.group(1))
        pending_link = await get_pending_player_link(server_name, code_hash)
        if not pending_link:
            return

        steam_id, player_name, lookup_error = await lookup_player(system_user, author)
        if lookup_error or not steam_id:
            logger.warning(
                "Could not resolve link verification author %s on %s: %s",
                author,
                server_name,
                lookup_error or "Steam ID unavailable",
            )
            await self._notify_user(
                pending_link["discord_id"],
                f"I saw the verification code from **{author}**, but could not resolve that player on **{server_name}**.",
            )
            return

        discord_id = pending_link["discord_id"]
        discord_ok, discord_link = await pb_client.find_player_link(
            "discord_id", discord_id
        )
        steam_ok, steam_link = await pb_client.find_player_link("steam_id", steam_id)
        if not discord_ok or not steam_ok:
            await self._notify_user(
                discord_id,
                "I confirmed the code, but the central player-link database is unavailable. Please try again with a new `/link` code.",
            )
            return

        if discord_link:
            if discord_link.get("steam_id") == steam_id:
                await consume_pending_player_link(pending_link["id"])
                await self._notify_user(
                    discord_id,
                    f"Your Discord account is already linked to **{player_name or author}**.",
                )
            else:
                await self._notify_user(
                    discord_id,
                    "Your Discord account is already linked to a different Steam account. Please contact an administrator to change it.",
                )
            return

        if steam_link:
            await self._notify_user(
                discord_id,
                "That Steam account is already linked to a different Discord account. Please contact an administrator if this is incorrect.",
            )
            return

        created = await pb_client.create_player_link(
            discord_id=discord_id,
            steam_id=steam_id,
            player_name=player_name or author,
            linked_from_server=server_name,
        )
        if not created:
            await self._notify_user(
                discord_id,
                "The link could not be saved. It may have just been linked elsewhere, or the central database may be unavailable.",
            )
            return

        await consume_pending_player_link(pending_link["id"])
        await self._notify_user(
            discord_id,
            f"Your Discord account is now linked to **{player_name or author}** on **{server_name}**. This link will work across the configured servers.",
        )

    async def _notify_user(self, discord_id: str, message: str):
        try:
            user = self.bot.get_user(int(discord_id))
            if user is None:
                user = await self.bot.fetch_user(int(discord_id))
            await user.send(message)
        except (discord.Forbidden, discord.HTTPException, ValueError) as e:
            logger.warning("Could not DM player-link user %s: %s", discord_id, e)
