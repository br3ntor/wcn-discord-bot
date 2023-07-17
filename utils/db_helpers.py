import aiosqlite


async def user_exists(server: str, usr: str) -> bool:
    """Check if a user exists in whitelist of server."""
    async with aiosqlite.connect(
        f"/home/pzserver{server}/Zomboid/db/pzserver.db"
    ) as db:
        async with db.execute(
            "SELECT * FROM whitelist WHERE username=?", [usr]
        ) as cursor:
            user_row = await cursor.fetchone()
            if user_row is not None:
                return True
            return False
