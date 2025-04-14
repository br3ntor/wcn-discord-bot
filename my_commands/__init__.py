from discord import app_commands

from .admin import admin_group
from .ban import ban_group
from .cat_fact import cat_fact
from .get_playerlist import get_playerlist
from .heal_player import heal_player
from .logs import logs_group
from .reset_password import reset_password
from .restart_server import restart_server
from .restart_server_auto import cancel_restart, restart_server_auto
from .send_message import send_message
from .speak import speak
from .update_mods_lists import update_mods_lists
from .update_sandbox_settings import update_sandbox_settings

restart_group = app_commands.Group(
    name="restart", description="Commands to control server restarts."
)

update_group = app_commands.Group(
    name="update", description="Commands to update github gists with game info."
)

restart_group.add_command(restart_server)
restart_group.add_command(restart_server_auto)
restart_group.add_command(cancel_restart)
update_group.add_command(update_mods_lists)
update_group.add_command(update_sandbox_settings)

__all__ = [
    "admin_group",
    "ban_group",
    "cat_fact",
    "get_playerlist",
    "heal_player",
    "logs_group",
    "reset_password",
    "restart_group",
    "send_message",
    "speak",
    # "update_group",
]
