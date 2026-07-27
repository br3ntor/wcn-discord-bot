import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent / "config"
DATA_DIR = Path(__file__).parent.parent / "data"


# This program is setup for one or more project zomboid servers running
# on the same machine with a single IP. Each game instance is run under
# its own user on a seperate port and managed as a systemd service.
class RconConfig(TypedDict):
    host: str
    port: int
    password: str


class LoggingConfig(TypedDict):
    chat: bool
    channel_id: Optional[int]


class ServerConfig(TypedDict):
    system_user: str
    server_name: str
    port: int
    rcon: RconConfig
    gists: Optional[Dict[str, str]]
    discord_playerlist: Optional[Dict[str, int]]
    logging: LoggingConfig


class CogConfig(TypedDict):
    enabled: bool
    class_name: str
    description: str
    requires_database: bool


def load_server_data(filepath: str) -> List[ServerConfig]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Server config file not found at {filepath}, using empty list.")
        return []
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {filepath}, using empty list.")
        return []


def load_cogs_config(filepath: str) -> Dict[str, CogConfig]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("cogs", {})
    except FileNotFoundError:
        logger.warning(f"Cogs config file not found at {filepath}, using empty config.")
        return {}
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {filepath}, using empty config.")
        return {}


class Config:
    # Required Env Vars - Program shouldn't run without these
    ANNOUNCE_CHANNEL: int
    MY_GUILD: int
    PZ_ADMIN_ROLE_ID: int
    MOD_CHANNEL: int
    DISCORD_TOKEN: Optional[str]

    # Optional Env Vars
    GITHUB_PAT: Optional[str]
    SERVER_PUB_IP: Optional[str]
    WEBHOOK_SECRET: Optional[str]
    SETTINGS_PATH: Optional[str]
    DB_PATH: Path

    KOFI_BILL_DAY: int
    KOFI_STARTING_AMOUNT: float
    KOFI_DONATION_GOAL: float

    POCKETBASE_URL: Optional[str]
    POCKETBASE_EMAIL: Optional[str]
    POCKETBASE_PASSWORD: Optional[str]
    pocketbase_configured: bool

    SERVER_DATA: List[ServerConfig]

    # Map server name to system user.
    SYSTEM_USERS: Dict[str, str]

    # Map system user to server name.
    SERVER_NAMES: Dict[str, str]

    COGS_CONFIG: Dict[str, CogConfig]

    @classmethod
    def init(cls):
        """Initialize config from environment variables and config files.

        Must be called from main.py before importing any other src modules
        that reference Config attributes.
        """
        load_dotenv()
        DATA_DIR.mkdir(exist_ok=True)

        # Required Env Vars
        cls.ANNOUNCE_CHANNEL = int(os.getenv("ANNOUNCE_CHANNEL", 0))
        cls.MY_GUILD = int(os.getenv("MY_GUILD", 0))
        cls.PZ_ADMIN_ROLE_ID = int(os.getenv("PZ_ADMIN_ROLE_ID", 0))
        cls.MOD_CHANNEL = int(os.getenv("MOD_CHANNEL", 0))
        cls.DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

        # Optional Env Vars
        cls.GITHUB_PAT = os.getenv("GITHUB_PAT")
        cls.SERVER_PUB_IP = os.getenv("SERVER_PUB_IP")
        cls.WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
        cls.SETTINGS_PATH = os.getenv("SETTINGS_PATH")

        db_path_env = os.getenv("DB_PATH")
        cls.DB_PATH = Path(db_path_env) if db_path_env else DATA_DIR / "bot_database.db"

        cls.KOFI_BILL_DAY = int(os.getenv("KOFI_BILL_DAY", 6))
        cls.KOFI_STARTING_AMOUNT = float(os.getenv("KOFI_STARTING_AMOUNT", 5))
        cls.KOFI_DONATION_GOAL = float(os.getenv("KOFI_DONATION_GOAL", 80))

        cls.POCKETBASE_URL = os.getenv("POCKETBASE_URL")
        cls.POCKETBASE_EMAIL = os.getenv("POCKETBASE_EMAIL")
        cls.POCKETBASE_PASSWORD = os.getenv("POCKETBASE_PASSWORD")
        cls.pocketbase_configured = all(
            [cls.POCKETBASE_URL, cls.POCKETBASE_EMAIL, cls.POCKETBASE_PASSWORD]
        )

        cls.SERVER_DATA = load_server_data(str(CONFIG_DIR / "servers.json"))

        cls.SYSTEM_USERS = {
            srv["server_name"]: srv["system_user"] for srv in cls.SERVER_DATA
        }

        cls.SERVER_NAMES = {
            srv["system_user"]: srv["server_name"] for srv in cls.SERVER_DATA
        }

        cls.COGS_CONFIG = load_cogs_config(str(CONFIG_DIR / "cogs.json"))

        logger.info("Config loaded")

    @staticmethod
    def get_rcon_config(server_name: str) -> Optional[ServerConfig]:
        for server in Config.SERVER_DATA:
            if server["server_name"] == server_name:
                return server
        return None

    @staticmethod
    def get_rcon_config_by_user(system_user: str) -> Optional[ServerConfig]:
        for server in Config.SERVER_DATA:
            if server["system_user"] == system_user:
                return server
        return None

    @staticmethod
    def validate():
        if not Config.ANNOUNCE_CHANNEL:
            raise EnvironmentError("ANNOUNCE_CHANNEL environment variable is not set")
        if not Config.DISCORD_TOKEN:
            raise EnvironmentError("DISCORD_TOKEN environment variable is not set")
        if not Config.MY_GUILD:
            raise EnvironmentError("MY_GUILD environment variable is not set")
        if not Config.PZ_ADMIN_ROLE_ID:
            raise EnvironmentError("PZ_ADMIN_ROLE_ID environment variable is not set")
        if not Config.MOD_CHANNEL:
            raise EnvironmentError("MOD_CHANNEL environment variable is not set")
        return True
