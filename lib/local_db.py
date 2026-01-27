import os
from datetime import datetime

import aiosqlite

db_path = "data/bot_database.db"


async def init_db():
    """Initialize the database and create tables if they don't exist."""
    global db_path

    # Convert to absolute path if relative path is given
    db_path = os.path.abspath(db_path)

    # Ensure the directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        # Create banned players table
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

        # Create donations table
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

        # Create ticket tracking table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                discord_message_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL,
                processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticket_id)
            )
            """
        )

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
                return 0.0  # Return 0 if no donations found or sum is NULL


# async def add_banned_player(player_name: str, steam_id: str) -> bool:
#     """Add a banned player to the database."""
#     try:
#         async with aiosqlite.connect(db_path) as db:
#             await db.execute(
#                 "INSERT INTO banned_players (player_name, steam_id) VALUES (?, ?)",
#                 (player_name, steam_id),
#             )
#             await db.commit()
#             return True
#     except aiosqlite.IntegrityError:  # Handle duplicate steam_id
#         return False
#
#
# async def remove_banned_player(steam_id: str) -> bool:
#     """Remove a banned player from the database."""
#     async with aiosqlite.connect(db_path) as db:
#         cursor = await db.execute(
#             "DELETE FROM banned_players WHERE steam_id = ?", (steam_id,)
#         )
#         await db.commit()
#         return cursor.rowcount > 0
#
#
# async def is_player_banned(steam_id: str) -> bool:
#     """Check if a player is banned."""
#     async with aiosqlite.connect(db_path) as db:
#         async with db.execute(
#             "SELECT 1 FROM banned_players WHERE steam_id = ?", (steam_id,)
#         ) as cursor:
#             return await cursor.fetchone() is not None


# async def get_player_total_donations(player_name: str) -> float:
#     """Get the total amount donated by a player."""
#     async with aiosqlite.connect(db_path) as db:
#         async with db.execute(
#             "SELECT SUM(amount) FROM donations WHERE player_name = ?",
#             (player_name,),
#         ) as cursor:
#             result = await cursor.fetchone()
#             # Handle case where result is None or first column is None
#             if result is None or result[0] is None:
#                 return 0.0
#             return float(result[0])
#
#
async def add_ticket_notification(ticket_id: int, discord_message_id: int, thread_id: int) -> bool:
    """Record that a ticket has been posted to Discord."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT INTO ticket_notifications (ticket_id, discord_message_id, thread_id) VALUES (?, ?, ?)",
                (ticket_id, discord_message_id, thread_id),
            )
            await db.commit()
            return True
    except aiosqlite.IntegrityError:  # Ticket already processed
        return False
    except Exception:
        return False


async def is_ticket_processed(ticket_id: int) -> bool:
    """Check if a ticket has already been processed."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT 1 FROM ticket_notifications WHERE ticket_id = ?", (ticket_id,)
        ) as cursor:
            return await cursor.fetchone() is not None


async def get_last_processed_ticket_id() -> int:
    """Get the highest ticket ID that has been processed."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT MAX(ticket_id) FROM ticket_notifications"
        ) as cursor:
            result = await cursor.fetchone()
            if result and result[0] is not None:
                return int(result[0])
            else:
                return 0  # Return 0 if no tickets have been processed


# async def get_recent_donations(limit: int = 5) -> Iterable[aiosqlite.Row]:
#     """Get recent donations with limit."""
#     async with aiosqlite.connect(db_path) as db:
#         # Ensure we get the results in the correct format
#         async with db.execute(
#             """SELECT player_name, amount, donation_date
#                FROM donations
#                ORDER BY donation_date DESC
#                LIMIT ?""",
#             (limit,),
#         ) as cursor:
#             results = await cursor.fetchall()
#             return results
#
#
# async def get_donations_since(
#     from_date: datetime,
# ) -> List[Tuple[str, float, str]]:
#     """
#     Get all donations since the specified date.
#
#     Args:
#         from_date (datetime): Return donations from this date onwards
#
#     Returns:
#         List[Tuple[str, float, str]]: List of tuples containing (player_name, amount, donation_date)
#     """
#     async with aiosqlite.connect(db_path) as db:
#         date_str = from_date.strftime("%Y-%m-%d %H:%M:%S")
#         query = """
#             SELECT player_name, amount, donation_date
#             FROM donations
#             WHERE donation_date >= ?
#             ORDER BY donation_date DESC
#         """
#
#         async with db.execute(query, (date_str,)) as cursor:
#             results = await cursor.fetchall()
#             return [(row[0], float(row[1]), row[2]) for row in results]
