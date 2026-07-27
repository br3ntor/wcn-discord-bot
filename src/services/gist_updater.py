import logging
from typing import Optional

import aiohttp

from src.config import Config
from src.services.server import (
    get_sandbox_vars_path,
    get_servers_workshop_ids,
    server_setting_paths,
)
from src.services.steam import get_servers_workshop_items

logger = logging.getLogger(__name__)

GITHUB_PAT = Config.GITHUB_PAT
SERVER_DATA = Config.SERVER_DATA


async def update_gist(
    content: str, filename: str, description: str, gist_id: str
) -> bool:
    """Update a GitHub gist with new content.

    Args:
        content: The content to write to the gist
        filename: Name of the file in the gist
        description: Description for the gist
        gist_id: The GitHub gist ID

    Returns:
        True if successful, False otherwise
    """
    url = f"https://api.github.com/gists/{gist_id}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "description": description,
        "files": {filename: {"content": content}},
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    logger.debug("Gist %s updated successfully", gist_id)
                    return True
                else:
                    logger.warning(
                        "Gist update failed for %s: status %s", gist_id, response.status
                    )
                    return False
    except Exception as e:
        logger.error("Error updating gist %s: %s", gist_id, e)
        return False


def get_sandbox_settings(system_user: str) -> Optional[str]:
    """Read sandbox settings file for a server.

    Args:
        system_user: The system user running the server

    Returns:
        File contents or None if file not found/error
    """
    file_path = get_sandbox_vars_path(system_user)
    try:
        with open(file_path) as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("Sandbox settings file not found: %s", file_path)
        return None
    except Exception as e:
        logger.error("Error reading sandbox settings for %s: %s", system_user, e)
        return None


def parse_workshop_data(workshop_items: list) -> str:
    """Parse workshop mod data to markdown for gist.

    Args:
        workshop_items: List of workshop item dictionaries

    Returns:
        Formatted markdown string
    """
    mods = []
    for item in workshop_items:
        if "title" in item:
            mods.append(
                f"[{item['title']}](https://steamcommunity.com/sharedfiles/filedetails/?id={item['publishedfileid']})\n\n"
            )
        else:
            logger.warning(
                "title is not in item: %s (result=%s)",
                item,
                item.get("result"),
            )

    mods.insert(0, f"**Mod Count: {len(mods)}**\n\n")
    sorted_mods = "".join(sorted(mods))

    return sorted_mods


async def update_all_modlist_gists() -> list[str]:
    """Update all mod list gists for configured servers.

    Returns:
        List of gist links that were updated
    """
    user_paths = await server_setting_paths()
    servers_workshop_ids = await get_servers_workshop_ids(user_paths)
    servers_mods = await get_servers_workshop_items(servers_workshop_ids)

    gist_links = []

    for zomboid_server in SERVER_DATA:
        system_user = zomboid_server["system_user"]
        server_name = zomboid_server["server_name"]

        if (
            system_user in servers_mods
            and zomboid_server["gists"] is not None
            and "modlist" in zomboid_server["gists"]
            and zomboid_server["gists"]["modlist"]
        ):
            data = parse_workshop_data(servers_mods[system_user])
            success = await update_gist(
                content=data,
                filename=f"{system_user}_mods.md",
                description=f"West Coast Noobs {server_name} Mods List",
                gist_id=zomboid_server["gists"]["modlist"],
            )

            if success:
                link = f"https://gist.github.com/br3ntor/{zomboid_server['gists']['modlist']}"
                gist_links.append(f"**{server_name}**: {link}")

    return gist_links


async def update_all_sandbox_gists() -> list[str]:
    """Update all sandbox settings gists for configured servers.

    Returns:
        List of gist links that were updated
    """
    gist_links = []

    for server in SERVER_DATA:
        if (
            server["gists"] is not None
            and "sandbox" in server["gists"]
            and server["gists"]["sandbox"]
        ):
            sandbox_settings = get_sandbox_settings(server["system_user"])
            if sandbox_settings is None:
                continue

            success = await update_gist(
                content=sandbox_settings,
                filename=f"{server['system_user']}_SandboxVars.lua",
                description=f"{server['server_name']} sandbox settings.",
                gist_id=server["gists"]["sandbox"],
            )

            if success:
                link = f"https://gist.github.com/br3ntor/{server['gists']['sandbox']}"
                gist_links.append(f"**{server['server_name']}**: {link}")

    return gist_links
