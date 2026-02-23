import asyncio
import logging
import os
from datetime import datetime, timezone

import aiosqlite
import discord
from discord.ext import commands, tasks

from src.config import Config

logger = logging.getLogger(__name__)
from src.services.bot_db import (
    add_ticket_notification,
    clear_ticket_notifications_for_server,
    get_last_processed_ticket_id,
    get_tracked_tickets,
    get_tracked_tickets_in_range,
    is_ticket_processed,
    update_ticket_state,
)

MOD_CHANNEL = Config.MOD_CHANNEL


class TicketWatcherCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ticket_thread_id = None
        self.retry_count = 0
        self.max_retries = 3
        self.server_last_ticket_ids = {}  # Track last ticket ID per server
        for server_config in Config.SERVER_DATA:
            self.server_last_ticket_ids[server_config["server_name"]] = 0

    async def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.ticket_monitor.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize the ticket watcher when bot is ready."""
        logger.info("Starting ticket watcher...")

        # Create or get the ticket thread
        await self.ensure_ticket_thread()

        # Sync with game database on startup
        await self.sync_with_game_database()

        # Start the monitoring loop
        self.ticket_monitor.start()

    async def sync_with_game_database(self):
        """Sync local tracking with current game database state on startup."""
        logger.info("Syncing with game databases...")

        if not self.ticket_thread_id:
            logger.warning("No ticket thread available for sync")
            return

        thread = self.bot.get_channel(self.ticket_thread_id)
        if not thread or not isinstance(thread, discord.Thread):
            logger.warning("Could not find ticket thread for sync")
            return

        total_tickets_added = 0
        total_tickets_skipped = 0

        for server_config in Config.SERVER_DATA:
            server_name = server_config["server_name"]
            system_user = server_config["system_user"]
            db_path = f"/home/{system_user}/Zomboid/db/pzserver.db"

            if not os.path.exists(db_path):
                logger.warning(f"Database not found for {server_name}: {db_path}")
                continue

            try:
                # Use read-only mode to avoid conflicts with PZ server
                async with aiosqlite.connect(
                    f"file:{db_path}?mode=ro", uri=True
                ) as pz_db:
                    async with pz_db.execute(
                        "SELECT id, message, author, answeredID FROM tickets WHERE answeredID IS NULL ORDER BY id ASC"
                    ) as cursor:
                        all_tickets = await cursor.fetchall()
                        ticket_count = sum(1 for _ in all_tickets) if all_tickets else 0

                logger.info(
                    f"Found {ticket_count} tickets in {server_name} database"
                )

                tickets_added = 0
                tickets_skipped = 0

                for ticket in all_tickets:
                    ticket_id, message, author, answered_id = ticket

                    # Check if we already have this ticket in our tracking (duplicate prevention)
                    if await is_ticket_processed(server_name, ticket_id):
                        tickets_skipped += 1
                        continue

                    # For original tickets, check if there's an answer (simplified 2-state system)
                    async with aiosqlite.connect(
                        f"file:{db_path}?mode=ro", uri=True
                    ) as pz_db:
                        answer = await self._find_answer_for_ticket(pz_db, ticket_id)
                        if answer:
                            state = "answered"
                        else:
                            state = "unanswered"

                        # Create embed for existing ticket
                        embed = discord.Embed(
                            title=f"🎫 [{server_name}] Support Ticket #{ticket_id}",
                            color=self._get_state_color(state),
                            timestamp=datetime.now(timezone.utc),
                        )
                        embed.add_field(
                            name="Status",
                            value=self._get_state_text(state),
                            inline=True,
                        )
                        embed.description = await self._build_ticket_description(
                            pz_db, ticket_id, message, author, answered_id
                        )
                        embed.set_footer(text="WCN Ticket System")

                        try:
                            discord_message = await thread.send(embed=embed)

                            # Record the notification
                            await add_ticket_notification(
                                server_name, ticket_id, discord_message.id, thread.id
                            )

                            # Update state tracking
                            await update_ticket_state(server_name, ticket_id, state)
                            tickets_added += 1

                            logger.info(
                                f"Added {server_name} ticket #{ticket_id} from {author}"
                            )

                        except discord.Forbidden:
                            logger.warning(
                                "Missing permissions to send messages during sync"
                            )
                            break
                        except Exception as e:
                            logger.error(
                                f"Error sending {server_name} ticket #{ticket_id} during sync: {e}"
                            )

                total_tickets_added += tickets_added
                total_tickets_skipped += tickets_skipped
                logger.info(
                    f"{server_name} sync completed - added {tickets_added} tickets, skipped {tickets_skipped} already tracked"
                )

            except aiosqlite.OperationalError as e:
                if "database is locked" in str(e).lower():
                    logger.warning(
                        f"{server_name} database locked during sync, will retry on next monitor cycle"
                    )
                else:
                    logger.error(
                        f"{server_name} database error during sync: {e}"
                    )
            except Exception as e:
                logger.error(f"Error during {server_name} database sync: {e}")

        logger.info(
            f"Overall sync completed - added {total_tickets_added} tickets, skipped {total_tickets_skipped} already tracked"
        )

    async def ensure_ticket_thread(self):
        """Create or retrieve the support tickets thread."""
        mod_channel = self.bot.get_channel(MOD_CHANNEL)
        if not mod_channel or not isinstance(mod_channel, discord.TextChannel):
            logger.error(f"Could not find mod channel {MOD_CHANNEL}")
            return

        # Try to find existing thread
        for thread in mod_channel.threads:
            if thread.name == "🎫 Support Tickets":
                self.ticket_thread_id = thread.id
                logger.info(f"Found existing ticket thread: {thread.id}")
                return

        # Create new thread if not found
        try:
            thread = await mod_channel.create_thread(
                name="🎫 Support Tickets",
                type=discord.ChannelType.public_thread,
                auto_archive_duration=1440,  # 24 hours
            )
            self.ticket_thread_id = thread.id
            logger.info(f"Created new ticket thread: {thread.id}")

            # Send initial message
            await thread.send(
                "🎫 **Support Ticket Monitor Started**\n\n"
                "This thread will automatically post new support tickets from the server database."
            )
        except discord.Forbidden:
            logger.warning("Missing permissions to create thread in mod channel")
        except Exception as e:
            logger.error(f"Error creating thread: {e}")

    @tasks.loop(seconds=30)
    async def ticket_monitor(self):
        """Monitor database for new support tickets and status changes."""
        if not self.ticket_thread_id:
            logger.debug("No thread ID set, skipping check")
            return

        try:
            # Get thread reference
            thread = self.bot.get_channel(self.ticket_thread_id)
            if not thread or not isinstance(thread, discord.Thread):
                logger.warning(f"Could not find thread {self.ticket_thread_id}")
                return

            # Process each server
            for server_config in Config.SERVER_DATA:
                server_name = server_config["server_name"]
                system_user = server_config["system_user"]
                db_path = f"/home/{system_user}/Zomboid/db/pzserver.db"

                if not os.path.exists(db_path):
                    logger.warning(
                        f"Database file not found for {server_name}: {db_path}"
                    )
                    continue

                try:
                    # Connect to PZ server database
                    async with aiosqlite.connect(db_path) as pz_db:
                        # Phase 1: Process new tickets
                        await self._process_new_tickets(server_name, pz_db, thread)

                        # Phase 2: Process status updates on tracked tickets
                        await self._process_status_updates(server_name, pz_db, thread)

                except aiosqlite.OperationalError as e:
                    if "database is locked" in str(e).lower():
                        logger.warning(
                            f"{server_name} database locked (attempt {self.retry_count + 1})"
                        )
                        self.retry_count += 1
                        if self.retry_count >= self.max_retries:
                            logger.warning(
                                "Max retries reached, stopping loop temporarily"
                            )
                            self.ticket_monitor.restart()
                    else:
                        logger.error(f"{server_name} database error: {e}")
                    continue  # Skip to next server
                except Exception as e:
                    logger.error(f"Unexpected error for {server_name}: {e}")
                    continue  # Skip to next server

            # Reset retry count on success
            self.retry_count = 0

        except Exception as e:
            logger.error(f"Unexpected error in monitor loop: {e}")

    async def _process_new_tickets(self, server_name: str, pz_db, thread):
        """Process and post new unanswered tickets."""
        # Check for game world reset
        async with pz_db.execute("SELECT MAX(id) FROM tickets") as cursor:
            result = await cursor.fetchone()
            game_max_id = result[0] if result and result[0] is not None else 0

        last_tracked_id = await get_last_processed_ticket_id(server_name)

        if game_max_id < last_tracked_id:
            logger.warning(
                f"Detected reset for {server_name} (last tracked: {last_tracked_id}, current max: {game_max_id}), resyncing..."
            )
            await clear_ticket_notifications_for_server(server_name)
            await self.sync_with_game_database()
            return

        # Query only for tickets after the last tracked ID (efficient - skip already processed)
        query = """
            SELECT id, message, author 
            FROM tickets 
            WHERE answeredID IS NULL AND id > ?
            ORDER BY id ASC
            LIMIT 20
        """

        async with pz_db.execute(query, (last_tracked_id,)) as cursor:
            new_tickets = await cursor.fetchall()

            if new_tickets:
                logger.info(
                    f"Found {len(new_tickets)} new tickets for {server_name} (last tracked: {last_tracked_id})"
                )

            for ticket in new_tickets:
                ticket_id, message, author = ticket

                # Skip if already processed (duplicate prevention)
                if await is_ticket_processed(server_name, ticket_id):
                    logger.debug(
                        f"The ticket # {ticket_id} looks processed for the {server_name}."
                    )
                    continue

                # Create and send embed
                embed = discord.Embed(
                    title=f"🎫 [{server_name}] New Support Ticket #{ticket_id}",
                    color=self._get_state_color("unanswered"),
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(
                    name="Status", value=self._get_state_text("unanswered"), inline=True
                )
                embed.description = await self._build_ticket_description(
                    pz_db, ticket_id, message, author, None
                )
                embed.set_footer(text="WCN Ticket System")

                try:
                    discord_message = await thread.send(embed=embed)

                    # Record the notification
                    await add_ticket_notification(
                        server_name, ticket_id, discord_message.id, thread.id
                    )

                    logger.info(
                        f"Posted {server_name} ticket #{ticket_id} from {author}"
                    )

                except discord.Forbidden:
                    logger.warning("Missing permissions to send messages")
                    break
                except Exception as e:
                    logger.error(f"Error sending message: {e}")

    async def _process_status_updates(self, server_name: str, pz_db, thread):
        """Process status updates for existing tracked tickets."""
        # Get valid ticket ID range from game DB
        async with pz_db.execute("SELECT MIN(id), MAX(id) FROM tickets") as cursor:
            row = await cursor.fetchone()
            min_id = row[0] if row and row[0] is not None else 0
            max_id = row[1] if row and row[1] is not None else 0

        # Only get tracked tickets within the current game DB range
        tracked_tickets = await get_tracked_tickets_in_range(
            server_name, min_id, max_id
        )

        # Count how many tickets actually need updates for progress tracking
        tickets_needing_updates = []
        for tracked_ticket in tracked_tickets:
            (
                tracked_server_name,
                ticket_id,
                discord_message_id,
                thread_id,
                last_state,
            ) = tracked_ticket

            # Only process tickets for this server
            if tracked_server_name != server_name:
                continue

            try:
                current_state = await self._determine_ticket_state(pz_db, ticket_id)
                # Skip deleted tickets (current_state is None) - we'll handle them in _update_ticket_embed
                if current_state is not None and current_state != last_state:
                    tickets_needing_updates.append(
                        (
                            ticket_id,
                            discord_message_id,
                            thread_id,
                            last_state,
                            current_state,
                        )
                    )
            except Exception as e:
                logger.error(
                    f"Error checking {server_name} ticket #{ticket_id}: {e}"
                )

        total_updates = len(tickets_needing_updates)

        # Show progress for large batches
        if total_updates > 5:
            logger.info(
                f"Processing {total_updates} {server_name} ticket updates..."
            )

        # Process the updates
        for i, (
            ticket_id,
            discord_message_id,
            thread_id,
            last_state,
            current_state,
        ) in enumerate(tickets_needing_updates):
            try:
                await self._update_ticket_embed(
                    server_name,
                    thread,
                    discord_message_id,
                    ticket_id,
                    current_state,
                    pz_db,
                )

                # Update our tracking
                await update_ticket_state(server_name, ticket_id, current_state)
                logger.info(
                    f"Updated {server_name} ticket #{ticket_id}: {last_state} → {current_state}"
                )

                # Show progress for large batches
                if total_updates > 5 and (i + 1) % 5 == 0:
                    logger.info(
                        f"Progress: {i + 1}/{total_updates} {server_name} updates completed"
                    )

            except discord.NotFound:
                logger.warning(
                    f"Message {discord_message_id} for {server_name} ticket #{ticket_id} not found"
                )
            except Exception as e:
                logger.error(
                    f"Error updating {server_name} ticket #{ticket_id}: {e}"
                )

        # Final progress update for large batches
        if total_updates > 5:
            logger.info(
                f"Completed {total_updates} {server_name} ticket updates"
            )

    async def _determine_ticket_state(self, pz_db, ticket_id):
        """Determine the current state of a ticket (simplified 2-state system)."""
        # Check if ticket still exists
        async with pz_db.execute(
            "SELECT answeredID, author FROM tickets WHERE id = ?", (ticket_id,)
        ) as cursor:
            result = await cursor.fetchone()

            if not result:
                return None  # Ticket no longer exists, we'll stop tracking it

            answered_id, author = result

            # Check if this ticket has an answer (for original tickets)
            answer = await self._find_answer_for_ticket(pz_db, ticket_id)
            if answer:
                return "answered"
            else:
                return "unanswered"

    async def _update_ticket_embed(
        self, server_name: str, thread, discord_message_id, ticket_id, state, pz_db
    ):
        """Update the Discord embed with new ticket status."""
        # Skip updates for deleted tickets (state is None)
        if state is None:
            logger.info(
                f"{server_name} ticket #{ticket_id} deleted, stopping tracking"
            )
            # Remove from local tracking database
            try:
                import aiosqlite

                from src.services.bot_db import db_path

                async with aiosqlite.connect(db_path) as db:
                    await db.execute(
                        "DELETE FROM ticket_notifications WHERE server_name = ? AND ticket_id = ?",
                        (
                            server_name,
                            ticket_id,
                        ),
                    )
                    await db.commit()
            except Exception as e:
                logger.error(
                    f"Error removing deleted {server_name} ticket #{ticket_id} from tracking: {e}"
                )
            return

        # Get ticket details for embed update
        async with pz_db.execute(
            "SELECT message, author, answeredID FROM tickets WHERE id = ?", (ticket_id,)
        ) as cursor:
            result = await cursor.fetchone()

        if not result:
            return  # Ticket was deleted, handled above

        message, author, answered_id = result

        # Create updated embed
        embed = discord.Embed(
            title=f"🎫 [{server_name}] Support Ticket #{ticket_id}",
            color=self._get_state_color(state),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Status", value=self._get_state_text(state), inline=True)
        embed.description = await self._build_ticket_description(
            pz_db, ticket_id, message, author, answered_id
        )
        embed.set_footer(text="WCN Ticket System")

        # Update the message using rate-safe editing
        try:
            discord_message = await thread.fetch_message(discord_message_id)
            success = await self.safe_message_edit(discord_message, embed=embed)
            if success:
                # Add conservative delay between updates
                await asyncio.sleep(0.6)
        except discord.NotFound:
            logger.warning(
                f"Could not find message {discord_message_id} for {server_name} ticket #{ticket_id} to edit"
            )
        except discord.Forbidden:
            logger.warning(
                f"Missing permissions to edit message {discord_message_id} for {server_name} ticket #{ticket_id}"
            )
        except Exception as e:
            logger.error(
                f"Error editing message {discord_message_id} for {server_name} ticket #{ticket_id}: {e}"
            )

    async def _get_answer_details(self, pz_db, answered_id):
        """Get full details about the ticket answer."""
        if not answered_id:
            return None

        async with pz_db.execute(
            "SELECT author, message FROM tickets WHERE id = ?", (answered_id,)
        ) as cursor:
            result = await cursor.fetchone()
            if result:
                return {"author": result[0], "message": result[1]}
            return None

    async def _get_original_ticket_details(self, pz_db, original_ticket_id):
        """Get details of the original ticket."""
        if not original_ticket_id:
            return None

        async with pz_db.execute(
            "SELECT author, message FROM tickets WHERE id = ?", (original_ticket_id,)
        ) as cursor:
            result = await cursor.fetchone()
            if result:
                return {"author": result[0], "message": result[1]}
            return None

    async def _find_answer_for_ticket(self, pz_db, original_ticket_id):
        """Find the single ticket that answers the original ticket."""
        if not original_ticket_id:
            return None

        async with pz_db.execute(
            "SELECT author, message FROM tickets WHERE answeredID = ?",
            (original_ticket_id,),
        ) as cursor:
            result = await cursor.fetchone()
            if result:
                return {"author": result[0], "message": result[1]}
            return None

    async def _build_ticket_description(
        self, pz_db, ticket_id, message, author, answered_id
    ):
        """Build the embed description with ticket and answer information."""
        if answered_id:
            # This ticket IS an answer, get the original question
            original_ticket = await self._get_original_ticket_details(
                pz_db, answered_id
            )
            if original_ticket:
                description = f"📝 **Ticket from {original_ticket['author']}:**\n{original_ticket['message']}\n\n💬 **Answer from {author}:**\n{message}"
            else:
                # Original ticket not found, display as regular ticket
                description = f"📝 **Ticket from {author}:**\n{message}"
        else:
            # This is an original ticket, check if it has an answer
            answer = await self._find_answer_for_ticket(pz_db, ticket_id)
            if answer:
                description = f"📝 **Ticket from {author}:**\n{message}\n\n💬 **Answer from {answer['author']}:**\n{answer['message']}"
            else:
                description = f"📝 **Ticket from {author}:**\n{message}"

        return description

    def _get_state_color(self, state):
        """Get Discord color for ticket state (simplified 2-state system)."""
        colors = {
            "unanswered": discord.Color.orange(),
            "answered": discord.Color.green(),
        }
        return colors.get(state, discord.Color.blue())

    def _get_state_text(self, state):
        """Get display text for ticket state (simplified 2-state system)."""
        texts = {
            "unanswered": "🔴 Unanswered",
            "answered": "✅ Answered",
        }
        return texts.get(state, "❓ Unknown")

    async def safe_message_edit(self, message, **kwargs):
        """Edit message with conservative retry based on Discord rate limit headers"""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                await message.edit(**kwargs)
                return True

            except discord.HTTPException as e:
                if e.status == 429 and attempt < max_retries - 1:
                    # Conservative approach: add extra buffer to Discord's wait time
                    retry_after = (
                        float(e.response.headers.get("Retry-After", 5000)) / 1000.0
                    )
                    wait_time = retry_after + 1.0  # Extra 1 second buffer

                    logger.warning(
                        f"[RateLimit] Conservative wait {wait_time:.2f}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Re-raise non-rate-limit errors or final attempt
                    raise

        return False

    @ticket_monitor.before_loop
    async def before_ticket_monitor(self):
        """Wait until the bot's internal cache is ready before starting the loop."""
        await self.bot.wait_until_ready()

    async def cog_load(self):
        """Auto-start monitoring when the cog is loaded."""
        logger.info("Cog loaded successfully")
