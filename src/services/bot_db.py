import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Coroutine, List, Tuple

import aiosqlite

from src.config import Config

logger = logging.getLogger(__name__)

db_path = (
    getattr(Config, "DB_PATH", None)
    or Path(__file__).parent.parent.parent / "data" / "bot_database.db"
)

SCHEMA_VERSION = 1

MIGRATIONS: List[Tuple[int, str, Callable[[aiosqlite.Connection], Coroutine]]] = []


def _migration(version: int, description: str) -> Callable[
    [Callable[[aiosqlite.Connection], Coroutine]],
    Callable[[aiosqlite.Connection], Coroutine],
]:
    """Decorator to register a migration function."""

    def decorator(
        fn: Callable[[aiosqlite.Connection], Coroutine],
    ) -> Callable[[aiosqlite.Connection], Coroutine]:
        MIGRATIONS.append((version, description, fn))
        return fn

    return decorator


@_migration(1, "Create initial schema")
async def _migrate_v1(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS banned_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            steam_id TEXT NOT NULL,
            banned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(steam_id)
        )
        """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            email TEXT NOT NULL,
            amount REAL NOT NULL,
            donation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS ticket_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_name TEXT NOT NULL,
            ticket_id INTEGER NOT NULL,
            discord_message_id INTEGER NOT NULL,
            thread_id INTEGER NOT NULL,
            processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_state TEXT DEFAULT 'unanswered',
            resolved_in_discord INTEGER DEFAULT 0,
            resolved_by TEXT DEFAULT NULL,
            UNIQUE(server_name, ticket_id)
        )
        """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS player_command_stats (
            steam_id TEXT NOT NULL,
            server_name TEXT NOT NULL,
            player_name TEXT NOT NULL,
            heal_count INTEGER DEFAULT 0,
            restore_levels_count INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(steam_id, server_name)
        )
        """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS command_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command_name TEXT NOT NULL,
            discord_user_id TEXT NOT NULL,
            discord_username TEXT NOT NULL,
            discord_roles TEXT,
            guild_id TEXT,
            channel_id TEXT,
            server_name TEXT,
            steam_id TEXT,
            player_name TEXT,
            arguments TEXT,
            success INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_command_history_steam_cmd
        ON command_history(steam_id, command_name)
        """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_command_history_cmd_time
        ON command_history(command_name, created_at)
        """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_command_history_user
        ON command_history(discord_user_id)
        """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS server_worlds (
            server_name TEXT PRIMARY KEY,
            world_started_at TEXT NOT NULL
        )
        """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS pending_player_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT NOT NULL,
            server_name TEXT NOT NULL,
            code_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            consumed_at TEXT
        )
        """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_pending_player_links_active
        ON pending_player_links(discord_id, server_name, consumed_at)
        """)


async def _get_schema_version(db: aiosqlite.Connection) -> int:
    cursor = await db.execute(
        "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
    )
    row = await cursor.fetchone()
    return row[0] if row else 0


async def _set_schema_version(db: aiosqlite.Connection, version: int) -> None:
    await db.execute("DELETE FROM schema_version")
    await db.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))


async def _has_legacy_tables(db: aiosqlite.Connection) -> bool:
    """Check for tables from a pre-v1 database that carries no version stamp."""
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name != 'schema_version'"
    ) as cursor:
        rows = await cursor.fetchall()
    return bool(rows)


async def init_db():
    """Initialize the database and apply any pending migrations."""
    global db_path

    db_path = db_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL
            )
        """)
        await db.commit()

        current_version = await _get_schema_version(db)

        if current_version == 0 and await _has_legacy_tables(db):
            logger.warning(
                f"Database at {db_path} has tables but no schema version stamp. "
                "The initial migration only creates missing tables, so it cannot "
                "add columns to existing ones. Delete this file to rebuild the "
                "schema from scratch."
            )

        if current_version < SCHEMA_VERSION:
            logger.info(
                f"Migrating database from version {current_version} to {SCHEMA_VERSION}"
            )
            for version, description, migrate_fn in MIGRATIONS:
                if current_version < version:
                    logger.info(f"Running migration v{version}: {description}")
                    await migrate_fn(db)
                    await _set_schema_version(db, version)
                    await db.commit()
            logger.info("Database migration completed")
        else:
            logger.info("Database schema is up to date")


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def upsert_server_world(server_name: str, world_started_at: datetime) -> bool:
    """Record when a server's current game world was created."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                INSERT INTO server_worlds (server_name, world_started_at)
                VALUES (?, ?)
                ON CONFLICT(server_name) DO UPDATE SET
                    world_started_at = excluded.world_started_at
                """,
                (server_name, world_started_at.astimezone(timezone.utc).isoformat()),
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Error upserting server world for {server_name}: {e}")
        return False


async def get_server_world_start(server_name: str) -> datetime | None:
    """Get the recorded world start date for a server, if known."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT world_started_at FROM server_worlds WHERE server_name = ?",
            (server_name,),
        ) as cursor:
            row = await cursor.fetchone()
    return _parse_utc(row[0]) if row else None


async def _stat_birth_time(path: str) -> datetime | None:
    """Get a filesystem path's creation time via GNU stat, or None if unknown."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "stat",
            "-c",
            "%W",
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return None
        epoch = int(stdout.decode().strip())
        if epoch <= 0:
            return None
        return datetime.fromtimestamp(epoch, timezone.utc)
    except Exception as e:
        logger.warning(f"Could not stat birth time for {path}: {e}")
        return None


async def sync_server_worlds(server_data: list) -> None:
    """Refresh world start dates from each server's save folder creation time.

    The PZ multiplayer save folder is recreated on every world wipe, so its
    filesystem birth time marks when the current world started.
    """
    for srv in server_data:
        server_name = srv["server_name"]
        save_name = srv.get("save_name", "pzserver")
        save_path = f"/home/{srv['system_user']}/Zomboid/Saves/Multiplayer/{save_name}"

        started_at = await _stat_birth_time(save_path)
        if started_at is None:
            logger.warning(
                f"Could not determine world start for {server_name} ({save_path}); "
                "keeping previous value"
            )
            continue

        if await upsert_server_world(server_name, started_at):
            logger.info(f"World start for {server_name}: {started_at.isoformat()}")


async def invalidate_pending_player_links(discord_id: str) -> None:
    """Invalidate all outstanding link codes for a Discord user."""
    consumed_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE pending_player_links
            SET consumed_at = ?
            WHERE discord_id = ? AND consumed_at IS NULL
            """,
            (consumed_at, discord_id),
        )
        await db.commit()


async def create_pending_player_link(
    discord_id: str,
    server_name: str,
    code_hash: str,
    expires_at: datetime,
) -> bool:
    """Store a temporary link code for a selected server."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                INSERT INTO pending_player_links
                    (discord_id, server_name, code_hash, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    discord_id,
                    server_name,
                    code_hash,
                    datetime.now(timezone.utc).isoformat(),
                    expires_at.astimezone(timezone.utc).isoformat(),
                ),
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error("Error creating pending player link: %s", e)
        return False


async def get_pending_player_link(server_name: str, code_hash: str) -> dict | None:
    """Return an unexpired pending link matching a server and code hash."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            """
            SELECT id, discord_id, server_name, code_hash, created_at, expires_at
            FROM pending_player_links
            WHERE server_name = ? AND code_hash = ? AND consumed_at IS NULL
            """,
            (server_name, code_hash),
        ) as cursor:
            row = await cursor.fetchone()

    if not row:
        return None

    if _parse_utc(row[5]) <= datetime.now(timezone.utc):
        return None

    return {
        "id": row[0],
        "discord_id": row[1],
        "server_name": row[2],
        "code_hash": row[3],
        "created_at": row[4],
        "expires_at": row[5],
    }


async def consume_pending_player_link(link_id: int) -> bool:
    """Consume a pending code exactly once."""
    consumed_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            UPDATE pending_player_links
            SET consumed_at = ?
            WHERE id = ? AND consumed_at IS NULL
            """,
            (consumed_at, link_id),
        )
        await db.commit()
        return cursor.rowcount == 1


async def get_active_pending_link_servers() -> set[str]:
    """Return servers with at least one unexpired pending link code."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("""
            SELECT DISTINCT server_name, expires_at
            FROM pending_player_links
            WHERE consumed_at IS NULL
            """) as cursor:
            rows = await cursor.fetchall()

    now = datetime.now(timezone.utc)
    return {row[0] for row in rows if _parse_utc(row[1]) > now}


async def cleanup_pending_player_links() -> None:
    """Remove consumed and expired temporary link records."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            DELETE FROM pending_player_links
            WHERE consumed_at IS NOT NULL OR expires_at <= ?
            """,
            (now,),
        )
        await db.commit()


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
            "SELECT 1 FROM ticket_notifications WHERE server_name = ? AND ticket_id = ?",
            (server_name, ticket_id),
        ) as cursor:
            return await cursor.fetchone() is not None


async def get_last_processed_ticket_id(server_name: str) -> int:
    """Get the highest ticket ID that has been processed for a specific server."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT MAX(ticket_id) FROM ticket_notifications WHERE server_name = ?",
            (server_name,),
        ) as cursor:
            result = await cursor.fetchone()
            if result and result[0] is not None:
                return int(result[0])
            else:
                return 0


async def get_tracked_tickets() -> list:
    """Get all tickets that have Discord notifications posted."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("""
            SELECT server_name, ticket_id, discord_message_id, thread_id, last_state
            FROM ticket_notifications
            ORDER BY server_name, ticket_id ASC
            """) as cursor:
            results = await cursor.fetchall()
            return [(row[0], row[1], row[2], row[3], row[4]) for row in results]


async def get_tracked_tickets_in_range(
    server_name: str, min_id: int, max_id: int
) -> list:
    """Get tracked tickets within a specific ID range."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            """SELECT server_name, ticket_id, discord_message_id, thread_id, last_state
               FROM ticket_notifications
               WHERE server_name = ? AND ticket_id BETWEEN ? AND ?
               ORDER BY ticket_id ASC""",
            (server_name, min_id, max_id),
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
            await db.execute(
                "DELETE FROM ticket_notifications WHERE server_name = ?", (server_name,)
            )
            await db.commit()
            return True
    except Exception:
        return False


async def get_ticket_by_discord_message(discord_message_id: int) -> tuple | None:
    """Look up a ticket by its Discord message ID."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT server_name, ticket_id, last_state, resolved_in_discord FROM ticket_notifications WHERE discord_message_id = ?",
            (discord_message_id,),
        ) as cursor:
            result = await cursor.fetchone()
            if result:
                return (result[0], result[1], result[2], result[3])
            return None


async def mark_ticket_resolved_in_discord(
    server_name: str, ticket_id: int, resolved_by: str
) -> bool:
    """Mark a ticket as resolved via Discord reaction."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE ticket_notifications SET last_state = ?, resolved_in_discord = 1, resolved_by = ? WHERE server_name = ? AND ticket_id = ?",
                ("answered", resolved_by, server_name, ticket_id),
            )
            await db.commit()
            return True
    except Exception:
        return False


async def revert_discord_resolution(server_name: str, ticket_id: int) -> bool:
    """Revert a Discord-only ticket resolution back to unanswered."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE ticket_notifications SET last_state = 'unanswered', resolved_in_discord = 0, resolved_by = NULL WHERE server_name = ? AND ticket_id = ?",
                (server_name, ticket_id),
            )
            await db.commit()
            return True
    except Exception:
        return False


async def get_discord_resolved_tickets(server_name: str) -> set:
    """Get all ticket IDs that were resolved via Discord for a server."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT ticket_id FROM ticket_notifications WHERE server_name = ? AND resolved_in_discord = 1",
            (server_name,),
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}


async def clear_discord_resolution_flag(server_name: str, ticket_id: int) -> bool:
    """Clear the discord resolution flag without changing last_state (e.g., game answer appeared)."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE ticket_notifications SET resolved_in_discord = 0, resolved_by = NULL WHERE server_name = ? AND ticket_id = ?",
                (server_name, ticket_id),
            )
            await db.commit()
            return True
    except Exception:
        return False


async def log_command_history(
    interaction,
    command_name: str,
    *,
    server_name: str | None = None,
    steam_id: str | None = None,
    player_name: str | None = None,
    arguments: dict | None = None,
    success: bool = True,
) -> bool:
    """Log one command invocation to the command_history table.

    Expects a discord.Interaction-like object; user, guild_id and channel_id
    are extracted automatically. Roles are stored as a JSON list of
    {"id", "name"} dicts, skipping @everyone.
    """
    user = interaction.user
    roles = [
        {"id": str(role.id), "name": role.name}
        for role in getattr(user, "roles", [])
        if not role.is_default()
    ]

    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                INSERT INTO command_history (
                    command_name, discord_user_id, discord_username, discord_roles,
                    guild_id, channel_id, server_name, steam_id, player_name,
                    arguments, success, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    command_name,
                    str(user.id),
                    str(user),
                    json.dumps(roles),
                    str(interaction.guild_id) if interaction.guild_id else None,
                    str(interaction.channel_id) if interaction.channel_id else None,
                    server_name,
                    steam_id,
                    player_name,
                    json.dumps(arguments) if arguments else None,
                    1 if success else 0,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Error logging command history: {e}")
        return False


async def get_latest_player_command(
    steam_id: str, server_name: str, command_name: str, player_name: str
) -> datetime | None:
    """Get the most recent successful use of a command by a player on a server.

    Scoped to the current world via server_worlds. Filters by character name
    for per-character cooldown checking. Returns the created_at timestamp or
    None if no matching record exists.
    """
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            """
            SELECT ch.created_at
            FROM command_history ch
            LEFT JOIN server_worlds sw ON sw.server_name = ch.server_name
            WHERE ch.steam_id = ?
              AND ch.server_name = ?
              AND ch.command_name = ?
              AND ch.player_name = ?
              AND ch.success = 1
              AND ch.created_at >= COALESCE(sw.world_started_at, '')
            ORDER BY ch.created_at DESC
            LIMIT 1
            """,
            (steam_id, server_name, command_name, player_name),
        ) as cursor:
            row = await cursor.fetchone()

    if not row:
        return None
    return _parse_utc(row[0])


async def get_player_command_counts_by_character(
    steam_id: str, server_name: str
) -> dict[str, dict[str, int]]:
    """Get per-character, per-command successful use counts on a server in the current world.

    Groups by (player_name, command_name). Returns a nested dict like:
        {"admin": {"heal_player": 2, "heal_self": 1}, "br3ntor": {"heal_self": 1}}
    """
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            """
            SELECT ch.player_name, ch.command_name, COUNT(*)
            FROM command_history ch
            LEFT JOIN server_worlds sw ON sw.server_name = ch.server_name
            WHERE ch.steam_id = ? AND ch.server_name = ? AND ch.success = 1
              AND ch.created_at >= COALESCE(sw.world_started_at, '')
            GROUP BY ch.player_name, ch.command_name
            """,
            (steam_id, server_name),
        ) as cursor:
            rows = await cursor.fetchall()

    result: dict[str, dict[str, int]] = {}
    for player_name, command_name, count in rows:
        if player_name not in result:
            result[player_name] = {}
        result[player_name][command_name] = count
    return result
