import asyncio

from config import Config
from lib.pzserver import pz_send_message

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES

# Track if countdown timer is running
countdown_isrunning = {server: False for server in SYSTEM_USERS.values()}

# Will abort all running countdowns
abort_signal = {"aborted": False}


# This whole restart countdown code might be better encapsulated in a class
# maybe a refactor project for the future.
async def restart_countdown_timer(system_user: str, duration: int):
    """Runs a countdown timer for the auto-restart, announcing the time remaining
    to the Project Zomboid server every minute.

    Args:
        system_user (str): The linux user running the server.
        duration (int): Time in seconds. Should be a multiple of 60.
    """
    # Start tracking running countdowns
    countdown_isrunning[system_user] = True
    seconds_left = duration
    while seconds_left > 0:
        if abort_signal["aborted"]:
            countdown_isrunning[system_user] = False
            abort_signal["aborted"] = False
            await pz_send_message(system_user, "Restart has been ABORTED")
            return False

        # Here we send restart msg to game server every minute
        if seconds_left % 60 == 0:
            await pz_send_message(
                system_user,
                f"The server will restart in {seconds_left//60} minute(s)!",
            )

        await asyncio.sleep(5)
        seconds_left -= 5
    countdown_isrunning[system_user] = False
    return True


def check_countdown_state(system_user: str) -> tuple[bool, str]:
    server_name = SERVER_NAMES[system_user]
    if countdown_isrunning[system_user]:
        return (
            False,
            f"There is already a countdown running for **{server_name}** server.",
        )
    if abort_signal["aborted"]:
        return False, f"Countdown abortion in progress for **{server_name}** server."
    return True, ""
