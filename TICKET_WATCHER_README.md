# Ticket Watcher Cog - Setup Instructions

## Overview
The Ticket Watcher Cog monitors your Project Zomboid server database for new support tickets and posts them to a Discord thread for your moderation team.

## Setup Requirements

### 1. Environment Variables
Add the following to your `.env` file:
```bash
MOD_CHANNEL=123456789012345678  # ID of your mod channel where the ticket thread will be created
```

### 2. Enable the Cog
Edit `cogs.json` and set `"enabled": true` for the ticket_watcher:
```json
"ticket_watcher": {
  "enabled": true,
  "class_name": "TicketWatcherCog",
  "description": "Monitors PZ server database for new support tickets",
  "requires_database": true
}
```

### 3. Database Access
Ensure the bot can read the PZ server database:
- The bot user needs read permissions on `/home/pzserver42/Zomboid/db/pzserver.db`
- If running as a different user, ensure proper permissions are set

### 4. Discord Permissions
The bot needs the following permissions in your mod channel:
- Create Threads
- Send Messages
- Read Message History

## How It Works

1. **Thread Creation**: On startup, creates a thread named "🎫 Support Tickets" in your mod channel
2. **Database Monitoring**: Every 60 seconds, checks for new tickets in the `tickets` table
3. **Duplicate Prevention**: Tracks all posted tickets in a local database to avoid duplicates
4. **Error Handling**: Includes retry logic for database locks and comprehensive error logging

## Features

- **Automatic Thread Management**: Creates and maintains a dedicated thread for ticket notifications
- **Rich Embeds**: Posts nicely formatted Discord embeds with ticket details
- **Smart Filtering**: Only posts unviewed tickets (viewed = 0)
- **Database Resilience**: Handles database locks with automatic retry logic
- **Duplicate Prevention**: Local tracking prevents re-notification of the same ticket

## Configuration Options

- **Check Frequency**: 60 seconds (configurable in the code)
- **Thread Auto-Archive**: 24 hours
- **Max Tickets Per Check**: 10 (to prevent spam)
- **Database Retries**: 3 attempts before temporary restart

## Database Schema

The cog extends your local bot database with a `ticket_notifications` table to track processed tickets.

## Troubleshooting

1. **Database not found**: Check the path `/home/pzserver42/Zomboid/db/pzserver.db` exists and is accessible
2. **Missing permissions**: Ensure the bot can create threads and send messages in your mod channel
3. **No thread created**: Check mod channel ID and bot permissions
4. **Duplicate notifications**: The local database should prevent this; check the `ticket_notifications` table