import asyncio
import os
from datetime import datetime, timezone

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import Config
from lib.local_db import (
    add_ticket_notification,
    get_last_processed_ticket_id,
    get_tracked_tickets,
    is_ticket_processed,
    update_ticket_state,
)

MOD_CHANNEL = Config.MOD_CHANNEL
PZSERVER_DB_PATH = "/home/pzserver42/Zomboid/db/pzserver.db"


class TicketWatcherCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ticket_thread_id = None
        self.retry_count = 0
        self.max_retries = 3

    async def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.ticket_monitor.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize the ticket watcher when bot is ready."""
        print("Starting ticket watcher...")

        # Create or get the ticket thread
        await self.ensure_ticket_thread()

        # Sync with game database on startup
        await self.sync_with_game_database()

        # Start the monitoring loop
        self.ticket_monitor.start()

    async def sync_with_game_database(self):
        """Sync local tracking with current game database state on startup."""
        if not os.path.exists(PZSERVER_DB_PATH):
            print(f"[TicketWatcher] Game database not found: {PZSERVER_DB_PATH}")
            return

        print("[TicketWatcher] Syncing with game database...")

        try:
            # Get all currently existing original tickets from game database (answeredID = NULL)
            # Use read-only mode to avoid conflicts with PZ server
            try:
                async with aiosqlite.connect(f"file:{PZSERVER_DB_PATH}?mode=ro", uri=True) as pz_db:
                    async with pz_db.execute(
                        "SELECT id, message, author, answeredID FROM tickets WHERE answeredID IS NULL ORDER BY id ASC"
                    ) as cursor:
                        all_tickets = await cursor.fetchall()
                        ticket_count = sum(1 for _ in all_tickets) if all_tickets else 0
            except aiosqlite.OperationalError as e:
                if "database is locked" in str(e).lower():
                    print(f"[TicketWatcher] Database locked during sync, will retry on next monitor cycle")
                    return
                else:
                    raise

            print(f"[TicketWatcher] Found {ticket_count} tickets in game database")

            # Only track tickets that exist in game database
            if not self.ticket_thread_id:
                print("[TicketWatcher] No ticket thread available for sync")
                return

            thread = self.bot.get_channel(self.ticket_thread_id)
            if not thread or not isinstance(thread, discord.Thread):
                print("[TicketWatcher] Could not find ticket thread for sync")
                return

            # Process all existing original tickets, but only add ones we don't already track
            tickets_added = 0
            tickets_skipped = 0
            
            for ticket in all_tickets:
                ticket_id, message, author, answered_id = ticket

                # Check if we already have this ticket in our tracking (duplicate prevention)
                if await is_ticket_processed(ticket_id):
                    tickets_skipped += 1
                    print(f"[TicketWatcher] Ticket #{ticket_id} already tracked, skipping")
                    continue

                # For original tickets, check if there's an answer (simplified 2-state system)
                answer = await self._find_answer_for_ticket(pz_db, ticket_id)
                if answer:
                    state = "answered"
                else:
                    state = "unanswered"

                # Create embed for existing ticket
                embed = discord.Embed(
                    title=f"🎫 Support Ticket #{ticket_id}",
                    color=self._get_state_color(state),
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(
                    name="Status", value=self._get_state_text(state), inline=True
                )
                embed.description = await self._build_ticket_description(
                    pz_db, ticket_id, message, author, answered_id
                )
                embed.set_footer(text="WCN Ticket System")

                try:
                    discord_message = await thread.send(embed=embed)

                    # Record the notification
                    await add_ticket_notification(
                        ticket_id, discord_message.id, thread.id
                    )

                    # Update state tracking
                    await update_ticket_state(ticket_id, state)
                    tickets_added += 1

                    print(f"[TicketWatcher] Added ticket #{ticket_id} from {author}")

                except discord.Forbidden:
                    print(
                        "[TicketWatcher] Missing permissions to send messages during sync"
                    )
                    break
                except Exception as e:
                    print(
                        f"[TicketWatcher] Error sending ticket #{ticket_id} during sync: {e}"
                    )

            print(f"[TicketWatcher] Sync completed - added {tickets_added} tickets, skipped {tickets_skipped} already tracked")

        except Exception as e:
            print(f"[TicketWatcher] Error during database sync: {e}")

    async def ensure_ticket_thread(self):
        """Create or retrieve the support tickets thread."""
        mod_channel = self.bot.get_channel(MOD_CHANNEL)
        if not mod_channel or not isinstance(mod_channel, discord.TextChannel):
            print(f"[TicketWatcher] Could not find mod channel {MOD_CHANNEL}")
            return

        # Try to find existing thread
        for thread in mod_channel.threads:
            if thread.name == "🎫 Support Tickets":
                self.ticket_thread_id = thread.id
                print(f"[TicketWatcher] Found existing ticket thread: {thread.id}")
                return

        # Create new thread if not found
        try:
            thread = await mod_channel.create_thread(
                name="🎫 Support Tickets",
                type=discord.ChannelType.public_thread,
                auto_archive_duration=1440,  # 24 hours
            )
            self.ticket_thread_id = thread.id
            print(f"[TicketWatcher] Created new ticket thread: {thread.id}")

            # Send initial message
            await thread.send(
                "🎫 **Support Ticket Monitor Started**\n\n"
                "This thread will automatically post new support tickets from the server database."
            )
        except discord.Forbidden:
            print("[TicketWatcher] Missing permissions to create thread in mod channel")
        except Exception as e:
            print(f"[TicketWatcher] Error creating thread: {e}")

    @tasks.loop(seconds=30)
    async def ticket_monitor(self):
        """Monitor database for new support tickets and status changes."""
        if not self.ticket_thread_id:
            print("[TicketWatcher] No thread ID set, skipping check")
            return

        if not os.path.exists(PZSERVER_DB_PATH):
            print(f"[TicketWatcher] Database file not found: {PZSERVER_DB_PATH}")
            return

        try:
            # Get thread reference
            thread = self.bot.get_channel(self.ticket_thread_id)
            if not thread or not isinstance(thread, discord.Thread):
                print(f"[TicketWatcher] Could not find thread {self.ticket_thread_id}")
                return

            # Connect to PZ server database
            async with aiosqlite.connect(PZSERVER_DB_PATH) as pz_db:
                # Phase 1: Process new tickets
                await self._process_new_tickets(pz_db, thread)

                # Phase 2: Process status updates on tracked tickets
                await self._process_status_updates(pz_db, thread)

            # Reset retry count on success
            self.retry_count = 0

        except aiosqlite.OperationalError as e:
            if "database is locked" in str(e).lower():
                print(
                    f"[TicketWatcher] Database locked (attempt {self.retry_count + 1})"
                )
                self.retry_count += 1
                if self.retry_count >= self.max_retries:
                    print(
                        "[TicketWatcher] Max retries reached, stopping loop temporarily"
                    )
                    self.ticket_monitor.restart()
            else:
                print(f"[TicketWatcher] Database error: {e}")
        except Exception as e:
            print(f"[TicketWatcher] Unexpected error: {e}")

    async def _process_new_tickets(self, pz_db, thread):
        """Process and post new unanswered tickets."""
        # Get last processed ticket ID
        last_ticket_id = await get_last_processed_ticket_id()

        # Query for new original tickets only (answeredID IS NULL)
        query = """
            SELECT id, message, author 
            FROM tickets 
            WHERE id > ? AND answeredID IS NULL
            ORDER BY id ASC
            LIMIT 10
        """

        async with pz_db.execute(query, (last_ticket_id,)) as cursor:
            new_tickets = await cursor.fetchall()

            for ticket in new_tickets:
                ticket_id, message, author = ticket

                # Skip if already processed (duplicate prevention)
                if await is_ticket_processed(ticket_id):
                    continue

                # Create and send embed
                embed = discord.Embed(
                    title=f"🎫 New Support Ticket #{ticket_id}",
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
                        ticket_id, discord_message.id, thread.id
                    )

                    print(f"[TicketWatcher] Posted ticket #{ticket_id} from {author}")

                except discord.Forbidden:
                    print("[TicketWatcher] Missing permissions to send messages")
                    break
                except Exception as e:
                    print(f"[TicketWatcher] Error sending message: {e}")

    async def _process_status_updates(self, pz_db, thread):
        """Process status updates for existing tracked tickets."""
        tracked_tickets = await get_tracked_tickets()

            # Count how many tickets actually need updates for progress tracking
        tickets_needing_updates = []
        for ticket_id, discord_message_id, thread_id, last_state in tracked_tickets:
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
                print(f"[TicketWatcher] Error checking ticket #{ticket_id}: {e}")

        total_updates = len(tickets_needing_updates)

        # Show progress for large batches
        if total_updates > 5:
            print(f"[TicketWatcher] Processing {total_updates} ticket updates...")

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
                    thread, discord_message_id, ticket_id, current_state, pz_db
                )

                # Update our tracking
                await update_ticket_state(ticket_id, current_state)
                print(
                    f"[TicketWatcher] Updated ticket #{ticket_id}: {last_state} → {current_state}"
                )

                # Show progress for large batches
                if total_updates > 5 and (i + 1) % 5 == 0:
                    print(
                        f"[TicketWatcher] Progress: {i + 1}/{total_updates} updates completed"
                    )

            except discord.NotFound:
                print(
                    f"[TicketWatcher] Message {discord_message_id} for ticket #{ticket_id} not found"
                )
            except Exception as e:
                print(f"[TicketWatcher] Error updating ticket #{ticket_id}: {e}")

        # Final progress update for large batches
        if total_updates > 5:
            print(f"[TicketWatcher] Completed {total_updates} ticket updates")

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
        self, thread, discord_message_id, ticket_id, state, pz_db
    ):
        """Update the Discord embed with new ticket status."""
        # Skip updates for deleted tickets (state is None)
        if state is None:
            print(f"[TicketWatcher] Ticket #{ticket_id} deleted, stopping tracking")
            # Remove from local tracking database
            try:
                import aiosqlite
                from lib.local_db import db_path
                async with aiosqlite.connect(db_path) as db:
                    await db.execute("DELETE FROM ticket_notifications WHERE ticket_id = ?", (ticket_id,))
                    await db.commit()
            except Exception as e:
                print(f"[TicketWatcher] Error removing deleted ticket #{ticket_id} from tracking: {e}")
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
            title=f"🎫 Support Ticket #{ticket_id}",
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
            print(
                f"[TicketWatcher] Could not find message {discord_message_id} to edit"
            )
        except discord.Forbidden:
            print(
                f"[TicketWatcher] Missing permissions to edit message {discord_message_id}"
            )
        except Exception as e:
            print(f"[TicketWatcher] Error editing message {discord_message_id}: {e}")

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

                    print(
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
        print("[TicketWatcher] Cog loaded successfully")
