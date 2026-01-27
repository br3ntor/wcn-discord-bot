import asyncio
import os
from datetime import datetime

import aiosqlite
import discord
from discord.ext import commands, tasks

from config import Config
from lib.local_db import add_ticket_notification, get_last_processed_ticket_id, is_ticket_processed

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
        self.ticket_watcher.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize the ticket watcher when bot is ready."""
        print("Starting ticket watcher...")
        
        # Create or get the ticket thread
        await self.ensure_ticket_thread()
        
        # Start the monitoring loop
        self.ticket_watcher.start()

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
                auto_archive_duration=1440  # 24 hours
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

    @tasks.loop(seconds=60)
    async def ticket_watcher(self):
        """Monitor database for new support tickets."""
        if not self.ticket_thread_id:
            print("[TicketWatcher] No thread ID set, skipping check")
            return

        if not os.path.exists(PZSERVER_DB_PATH):
            print(f"[TicketWatcher] Database file not found: {PZSERVER_DB_PATH}")
            return

        try:
            # Get last processed ticket ID
            last_ticket_id = await get_last_processed_ticket_id()
            
            # Connect to PZ server database
            async with aiosqlite.connect(PZSERVER_DB_PATH) as pz_db:
                # Query for new tickets
                query = """
                    SELECT id, message, author 
                    FROM tickets 
                    WHERE id > ? AND viewed = 0 
                    ORDER BY id ASC
                    LIMIT 10
                """
                
                async with pz_db.execute(query, (last_ticket_id,)) as cursor:
                    new_tickets = await cursor.fetchall()
                    
                    if new_tickets:
                        thread = self.bot.get_channel(self.ticket_thread_id)
                        if not thread or not isinstance(thread, discord.Thread):
                            print(f"[TicketWatcher] Could not find thread {self.ticket_thread_id}")
                            return
                        
                        for ticket in new_tickets:
                            ticket_id, message, author = ticket
                            
                            # Skip if already processed (duplicate prevention)
                            if await is_ticket_processed(ticket_id):
                                continue
                            
                            # Create and send embed
                            embed = discord.Embed(
                                title=f"🎫 New Support Ticket #{ticket_id}",
                                color=discord.Color.orange(),
                                timestamp=datetime.utcnow()
                            )
                            embed.add_field(name="Author", value=author, inline=True)
                            embed.add_field(name="Status", value="🔴 Unviewed", inline=True)
                            embed.description = f"**Message:**\n{message}"
                            embed.set_footer(text="Support Ticket System")
                            
                            try:
                                discord_message = await thread.send(embed=embed)
                                
                                # Record the notification
                                await add_ticket_notification(
                                    ticket_id, 
                                    discord_message.id, 
                                    thread.id
                                )
                                
                                print(f"[TicketWatcher] Posted ticket #{ticket_id} from {author}")
                                
                            except discord.Forbidden:
                                print("[TicketWatcher] Missing permissions to send messages")
                                break
                            except Exception as e:
                                print(f"[TicketWatcher] Error sending message: {e}")
                    
                    # Reset retry count on success
                    self.retry_count = 0
                    
        except aiosqlite.OperationalError as e:
            if "database is locked" in str(e).lower():
                print(f"[TicketWatcher] Database locked (attempt {self.retry_count + 1})")
                self.retry_count += 1
                if self.retry_count >= self.max_retries:
                    print("[TicketWatcher] Max retries reached, stopping loop temporarily")
                    self.ticket_watcher.restart()
            else:
                print(f"[TicketWatcher] Database error: {e}")
        except Exception as e:
            print(f"[TicketWatcher] Unexpected error: {e}")

    @ticket_watcher.before_loop
    async def before_ticket_watcher(self):
        """Wait until the bot's internal cache is ready before starting the loop."""
        await self.bot.wait_until_ready()

    async def cog_load(self):
        """Auto-start monitoring when the cog is loaded."""
        print("[TicketWatcher] Cog loaded successfully")