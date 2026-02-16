import asyncio

from src.config import Config
from src.utils.pzserver import pz_send_message

ANNOUNCE_CHANNEL = Config.ANNOUNCE_CHANNEL
SYSTEM_USERS = Config.SYSTEM_USERS
SERVER_NAMES = Config.SERVER_NAMES

# Track if countdown timer is running
countdown_isrunning = {server: False for server in SYSTEM_USERS.values()}

# Will abort all running countdowns
abort_signal = {"aborted": False}


async def restart_countdown_timer(system_user: str, duration: int) -> tuple[bool, str]:
    """Runs a countdown timer for the auto-restart, announcing the time remaining
    to the Project Zomboid server every minute.

    Args:
        system_user (str): The linux user running the server.
        duration (int): Time in seconds. Should be a multiple of 60.
    Returns:
        tuple[bool, str]:  A tuple where the first element is a boolean indicating success (True) or
        failure (False), and the second element is either an empty string (for success) or a
        descriptive error message (for failure).
    """

    server_name = SERVER_NAMES[system_user]

    # Should never run if countdown is already running or abort signal is true
    if countdown_isrunning[system_user]:
        return (
            False,
            f"There is already a countdown running for **{server_name}** server.",
        )
    if abort_signal["aborted"]:
        return False, f"Countdown abort in progress for **{server_name}** server."

    # Start tracking running countdowns
    countdown_isrunning[system_user] = True
    seconds_left = duration
    while seconds_left > 0:
        if abort_signal["aborted"]:
            countdown_isrunning[system_user] = False

            # Only set aborted to false if all countdowns are false
            if not any(countdown_isrunning.values()):
                abort_signal["aborted"] = False

            # Msg to the game server
            await pz_send_message(system_user, "Restart has been ABORTED")

            return False, f"Auto restart ABORTED 👼 for the **{server_name}** server."

        # Here we send restart msg to game server every minute
        if seconds_left % 60 == 0:
            await pz_send_message(
                system_user,
                f"The server will restart in {seconds_left//60} minute(s)!",
            )

        await asyncio.sleep(5)
        seconds_left -= 5
    countdown_isrunning[system_user] = False
    return True, ""
