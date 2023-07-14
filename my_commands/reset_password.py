import sqlite3
import discord
from discord import app_commands


@app_commands.command()
@app_commands.choices(
    server=[
        app_commands.Choice(name="Light", value=1),
        app_commands.Choice(name="Heavy", value=2),
    ]
)
async def reset_password(
    interaction: discord.Interaction, server: app_commands.Choice[int], playername: str
):
    """Reset a players password."""
    attempted_reset_response = sql_reset_pwd(server.name, playername)
    await interaction.response.send_message(attempted_reset_response)

# TODO: Refactor this with aiosqlite. Since the db is close and access is fast it works fine as is but...
def sql_reset_pwd(server: str, player: str) -> str:
    db_path = {
        "light": "/home/pzserverlight/Zomboid/db/pzserver.db",
        "heavy": "/home/pzserverheavy/Zomboid/db/pzserver.db",
    }

    db = sqlite3.connect(db_path[server.lower()])

    cursor = db.cursor()

    user_row = cursor.execute(
        "SELECT * FROM whitelist WHERE username=?", [player]
    ).fetchone()

    if user_row is None:
        db.close()
        print("No user found")
        return f"Couldn't find user {player} on {server} server"

    print(f"User {player} has been found")
    cursor.execute(
        "UPDATE whitelist SET password=? WHERE _rowid_=?",
        (None, user_row[0]),
    )
    db.commit()

    pwd = cursor.execute(
        "SELECT password FROM whitelist WHERE username=?", [player]
    ).fetchone()[0]
    db.close()

    if pwd is None:
        print(f"reset {player} on {server}")
        return f"{player}'s password has been reset on the {server} server. They may login with any new password."
    else:
        print("Something went wrong")
        return "Something went wrong, contact brent"
