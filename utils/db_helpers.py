import aiosqlite
from typing import Optional


async def get_user(server: str, username: str) -> Optional[aiosqlite.Row]:
    """Return the db row for a players."""
    async with aiosqlite.connect(
        f"/home/pzserver{server}/Zomboid/db/pzserver.db"
    ) as db:
        async with db.execute(
            "SELECT * FROM whitelist WHERE username=?", [username]
        ) as cursor:
            return await cursor.fetchone()


async def get_banned_user(server: str, steamid: str) -> Optional[aiosqlite.Row]:
    """Return the db row for a banned player."""
    async with aiosqlite.connect(
        f"/home/pzserver{server}/Zomboid/db/pzserver.db"
    ) as db:
        async with db.execute(
            "SELECT * FROM bannedid WHERE steamid=?", [steamid]
        ) as cursor:
            return await cursor.fetchone()
