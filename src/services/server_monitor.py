import asyncio
import logging
import time

import discord

from src.config import Config
from src.services.pz_server import wait_for_server_up

logger = logging.getLogger(__name__)

_active_monitors: set[asyncio.Task] = set()


def _format_elapsed(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


async def monitor_restart(
    system_user: str,
    server_name: str,
    announce_chan: discord.TextChannel,
    max_wait: float = 900.0,
) -> None:
    """Waits for a restarted server to accept RCON commands, then announces it.

    Posts a success message to the announce channel once the server responds
    to RCON, or alerts the mod channel if it does not come up within max_wait.
    Never raises — Discord failures are logged instead.
    """
    try:
        mod_chan = announce_chan.guild.get_channel(Config.MOD_CHANNEL)
        if not isinstance(mod_chan, discord.TextChannel):
            logger.error(
                "Could not find mod channel %s for restart alerting",
                Config.MOD_CHANNEL,
            )
            mod_chan = None

        started = time.monotonic()
        up = await wait_for_server_up(system_user, max_wait=max_wait)
        elapsed = _format_elapsed(time.monotonic() - started)

        if up:
            await announce_chan.send(
                f"✅ The **{server_name}** server is back up! (took {elapsed})"
            )
            return

        alert = (
            f"⚠️ The **{server_name}** server did not come back up "
            f"within {int(max_wait // 60)} minutes of restarting."
        )
        if mod_chan is not None:
            await mod_chan.send(alert)
        else:
            logger.error(alert)
    except Exception:
        logger.exception("Restart monitor for %s (%s) failed", server_name, system_user)


def start_restart_monitor(
    system_user: str,
    server_name: str,
    announce_chan: discord.TextChannel,
    max_wait: float = 900.0,
) -> asyncio.Task:
    """Starts monitor_restart as a background task held against GC."""
    task = asyncio.create_task(
        monitor_restart(system_user, server_name, announce_chan, max_wait)
    )
    _active_monitors.add(task)
    task.add_done_callback(_active_monitors.discard)
    return task
