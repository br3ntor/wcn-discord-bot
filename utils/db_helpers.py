import aiosqlite
from typing import Optional


async def get_user(username: str) -> Optional[aiosqlite.Row]:
    """Return the db row for a players."""
    async with aiosqlite.connect("/home/pzserver/Zomboid/db/pzserver.db") as db:
        async with db.execute(
            "SELECT * FROM whitelist WHERE username=?", [username]
        ) as cursor:
            return await cursor.fetchone()


async def get_banned_user(steamid: str) -> Optional[aiosqlite.Row]:
    """Return the db row for a banned player."""
    async with aiosqlite.connect("/home/pzserver/Zomboid/db/pzserver.db") as db:
        async with db.execute(
            "SELECT * FROM bannedid WHERE steamid=?", [steamid]
        ) as cursor:
            return await cursor.fetchone()
