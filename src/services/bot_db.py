from datetime import datetime
from pathlib import Path

import aiosqlite

project_root = Path(__file__).parent.parent.parent
db_path = project_root / "data" / "bot_database.db"


async def init_db():
    """Initialize the database and create tables if they don't exist."""
    global db_path

    db_path = db_path.resolve()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS banned_players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                steam_id TEXT NOT NULL,
                banned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(steam_id)
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS donations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                email TEXT NOT NULL,
                amount REAL NOT NULL,
                donation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_name TEXT NOT NULL,
                ticket_id INTEGER NOT NULL,
                discord_message_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL,
                processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_state TEXT DEFAULT 'unanswered',
                UNIQUE(server_name, ticket_id)
            )
            """
        )

        try:
            async with db.execute("PRAGMA table_info(ticket_notifications)") as cursor:
                columns = await cursor.fetchall()
                has_server_name = any(col[1] == 'server_name' for col in columns)
            
            if not has_server_name:
                print("[DB] Migrating ticket_notifications table to support multiple servers")
                await db.execute("DROP TABLE IF EXISTS ticket_notifications")
                await db.execute(
                    """
                    CREATE TABLE ticket_notifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        server_name TEXT NOT NULL,
                        ticket_id INTEGER NOT NULL,
                        discord_message_id INTEGER NOT NULL,
                        thread_id INTEGER NOT NULL,
                        processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_state TEXT DEFAULT 'unanswered',
                        UNIQUE(server_name, ticket_id)
                    )
                    """
                )
                print("[DB] Migration completed - now supporting multiple servers")
        except Exception as e:
            print(f"[DB] Error during migration: {e}")

        await db.commit()
        print("Database exists!")


async def add_donation(player_name: str, email: str, amount: float) -> bool:
    """Record a donation from a player."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT INTO donations (player_name, email, amount) VALUES (?, ?, ?)",
                (player_name, email, amount),
            )
            await db.commit()
            return True
    except Exception:
        return False


async def get_total_donations_since(from_date: datetime) -> float:
    """
    Get the total sum of donations since the specified date.

    Args:
        from_date (datetime): Sum donations from this date onwards

    Returns:
        float: Total sum of donations.
    """
    async with aiosqlite.connect(db_path) as db:
        date_str = from_date.strftime("%Y-%m-%d %H:%M:%S")
        query = """
            SELECT SUM(amount)
            FROM donations
            WHERE donation_date >= ?
        """

        async with db.execute(query, (date_str,)) as cursor:
            result = await cursor.fetchone()
            if result and result[0] is not None:
                return float(result[0])
            else:
                return 0.0


async def add_ticket_notification(
    server_name: str, ticket_id: int, discord_message_id: int, thread_id: int
) -> bool:
    """Record that a ticket has been posted to Discord."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT INTO ticket_notifications (server_name, ticket_id, discord_message_id, thread_id, last_state) VALUES (?, ?, ?, ?, ?)",
                (server_name, ticket_id, discord_message_id, thread_id, "unanswered"),
            )
            await db.commit()
            return True
    except aiosqlite.IntegrityError:
        return False
    except Exception:
        return False


async def is_ticket_processed(server_name: str, ticket_id: int) -> bool:
    """Check if a ticket has already been processed."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT 1 FROM ticket_notifications WHERE server_name = ? AND ticket_id = ?", (server_name, ticket_id)
        ) as cursor:
            return await cursor.fetchone() is not None


async def get_last_processed_ticket_id(server_name: str) -> int:
    """Get the highest ticket ID that has been processed for a specific server."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT MAX(ticket_id) FROM ticket_notifications WHERE server_name = ?", (server_name,)
        ) as cursor:
            result = await cursor.fetchone()
            if result and result[0] is not None:
                return int(result[0])
            else:
                return 0


async def get_tracked_tickets() -> list:
    """Get all tickets that have Discord notifications posted."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            """
            SELECT server_name, ticket_id, discord_message_id, thread_id, last_state
            FROM ticket_notifications
            ORDER BY server_name, ticket_id ASC
            """
        ) as cursor:
            results = await cursor.fetchall()
            return [(row[0], row[1], row[2], row[3], row[4]) for row in results]


async def get_tracked_tickets_in_range(server_name: str, min_id: int, max_id: int) -> list:
    """Get tracked tickets within a specific ID range."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            """SELECT server_name, ticket_id, discord_message_id, thread_id, last_state
               FROM ticket_notifications 
               WHERE server_name = ? AND ticket_id BETWEEN ? AND ?
               ORDER BY ticket_id ASC""",
            (server_name, min_id, max_id)
        ) as cursor:
            results = await cursor.fetchall()
            return [(row[0], row[1], row[2], row[3], row[4]) for row in results]


async def clear_ticket_notifications_for_server(server_name: str):
    """Remove all ticket tracking for a server (used on game world reset)."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "DELETE FROM ticket_notifications WHERE server_name = ?", (server_name,)
        )
        await db.commit()


async def update_ticket_state(server_name: str, ticket_id: int, new_state: str) -> bool:
    """Update the last known state of a ticket."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE ticket_notifications SET last_state = ? WHERE server_name = ? AND ticket_id = ?",
                (new_state, server_name, ticket_id),
            )
            await db.commit()
            return True
    except Exception:
        return False


async def get_ticket_last_state(server_name: str, ticket_id: int) -> str:
    """Get the last known state of a ticket."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT last_state FROM ticket_notifications WHERE server_name = ? AND ticket_id = ?",
            (server_name, ticket_id),
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else "unanswered"


async def clear_local_tracking() -> bool:
    """Clear all ticket notifications from local database."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("DELETE FROM ticket_notifications")
            await db.commit()
            return True
    except Exception:
        return False


async def clear_server_tracking(server_name: str) -> bool:
    """Clear all ticket notifications for a specific server from local database."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("DELETE FROM ticket_notifications WHERE server_name = ?", (server_name,))
            await db.commit()
            return True
    except Exception:
        return False
