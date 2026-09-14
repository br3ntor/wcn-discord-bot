from discord import app_commands

from .additem import additem
from .addvehicle import addvehicle
from .admin import admin_group
from .cat_fact import cat_fact
from .chat_summary import chat_summary
from .get_playerlist import get_playerlist
from .godmode import godmode_group
from .heal_player import heal_player
from .heal_self import heal_self
from .kick_player import kick_player
from .logs import logs_group
from .player_stats import player_stats
from .restart_server import restart_server
from .restart_server_auto import cancel_restart, restart_server_auto
from .restore_self import restore_self
from .restore_skills import restore_levels
from .send_message import send_message
from .server_settings import server_settings
from .speak import speak
from .teleport import teleport

restart_group = app_commands.Group(
    name="restart", description="Commands to control server restarts."
)

restart_group.add_command(restart_server)
restart_group.add_command(restart_server_auto)
restart_group.add_command(cancel_restart)

__all__ = [
    "additem",
    "addvehicle",
    "admin_group",
    "cat_fact",
    "chat_summary",
    "get_playerlist",
    "godmode_group",
    "heal_player",
    "heal_self",
    "kick_player",
    "logs_group",
    "player_stats",
    "restart_group",
    "send_message",
    "speak",
    "teleport",
    "server_settings",
    "restore_levels",
    "restore_self",
]
