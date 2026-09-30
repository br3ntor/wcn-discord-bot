"""One-off backfill: expand player_command_stats counters into command_history rows.

Each row in player_command_stats becomes `heal_count` rows of 'heal_player' and
`restore_levels_count` rows of 'restore_levels' in command_history, with
created_at set to the old row's last_updated timestamp.

Safe to run once: aborts if backfilled rows already exist.

Usage:
    source .venv/bin/activate
    python scripts/backfill_command_history.py
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import aiosqlite

from src.services import bot_db

BACKFILL_MARKER = "backfill"


def _normalize_timestamp(value: str) -> str:
    """Convert SQLite CURRENT_TIMESTAMP format to ISO-8601 UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


async def main() -> None:
    await bot_db.init_db()

    async with aiosqlite.connect(bot_db.db_path) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM command_history WHERE discord_user_id = ?",
            (BACKFILL_MARKER,),
        ) as cursor:
            existing = (await cursor.fetchone())[0]
        if existing:
            print(f"Aborting: {existing} backfilled rows already exist.")
            return

        async with db.execute("""
            SELECT steam_id, server_name, player_name, heal_count,
                   restore_levels_count, last_updated
            FROM player_command_stats
            """) as cursor:
            old_rows = await cursor.fetchall()

        inserted = 0
        for steam_id, server_name, player_name, heals, restores, updated in old_rows:
            created_at = _normalize_timestamp(updated)
            for command_name, count in (
                ("heal_player", heals),
                ("restore_levels", restores),
            ):
                for _ in range(count):
                    await db.execute(
                        """
                        INSERT INTO command_history (
                            command_name, discord_user_id, discord_username,
                            server_name, steam_id, player_name, success, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                        """,
                        (
                            command_name,
                            BACKFILL_MARKER,
                            BACKFILL_MARKER,
                            server_name,
                            steam_id,
                            player_name,
                            created_at,
                        ),
                    )
                    inserted += 1

        await db.commit()

    print(
        f"Done: inserted {inserted} rows from {len(old_rows)} player_command_stats rows."
    )


if __name__ == "__main__":
    asyncio.run(main())
