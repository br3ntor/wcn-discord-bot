import asyncio
import configparser
import os

from config import Config

SERVER_DATA = Config.SERVER_DATA
SERVER_NAMES = Config.SERVER_NAMES


async def server_isrunning(server: str) -> bool:
    """Check if the given zomboid server name is running"""
    cmd = [
        "ps",
        "-f",
        "-u",
        server,
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
        )

        # Get the output of the subprocess.
        output, error = await process.communicate()

    except Exception as e:
        # FIX: Find correct exception sometime
        print(f"Subprocess error occurred: {e}")

    out, err = output.decode(), error.decode()

    # High skill error handling
    if err:
        print(err)

    for line in out.splitlines():
        if "ProjectZomboid64" in line:
            print(f"{server} is running:\n{line}")
            return True

    return False


async def server_setting_paths() -> list:
    """Return list of paths to running servers settings files"""
    server_files = []
    servers_with_gists = [
        server["system_user"] for server in SERVER_DATA if server["gists"]
    ]
    for username in servers_with_gists:
        if await server_isrunning(username):
            server_files.append(f"/home/{username}/Zomboid/Server/pzserver.ini")
    return server_files


# Pure slop lol, but good slop?
async def get_servers_workshop_ids(
    file_paths: list[str],
) -> dict[str, list[str]]:
    """
    Returns running server names (which are the usernames) with their workshop ids.
    Assumes the file path is like '/home/{username}/Zomboid/Server/pzserver.ini'.
    """

    print(f"Processing server config files from paths: {file_paths}")
    servers_workshopids_lists: dict[str, list[str]] = {}

    for path in file_paths:
        print(f"Attempting to process file: {path}")
        server_name = ""
        try:
            # Extract the username from the path
            # For '/home/{username}/Zomboid/Server/pzserver.ini',
            # split('/') gives ['', 'home', 'username', 'Zomboid', 'Server', 'pzserver.ini']
            # So, index 2 will be 'username'.
            parts = path.split(os.sep)  # Use os.sep for cross-platform compatibility
            if len(parts) > 2 and parts[1] == "home":  # Ensure it's a /home/user path
                server_name = parts[2]
            else:
                print(
                    f"Warning: Could not determine username from path: {path}. Skipping this file."
                )
                continue

            if not server_name:
                print(
                    f"Warning: Server name (username) is empty for path: {path}. Skipping this file."
                )
                continue

            config = configparser.ConfigParser()
            with open(path, "r") as stream:
                # configparser needs a section header, so we add '[default]'
                config.read_string("[default]\n" + stream.read())

            # Ensure the 'default' section exists before trying to access keys
            if "default" not in config:
                print(
                    f"Warning: '[default]' section not found in {path} for server '{server_name}'. Skipping."
                )
                continue

            # Safely get 'WorkshopItems', defaulting to an empty string if not found
            workshop_items_str = config["default"].get("WorkshopItems", "")

            # If 'WorkshopItems' is empty or not present, skip
            if not workshop_items_str:
                print(
                    f"Info: No 'WorkshopItems' found or it's empty for server '{server_name}' in {path}."
                )
                continue

            # Split by semicolon and clean up each item (remove whitespace, skip empty strings)
            workshop_ids = [
                item.strip() for item in workshop_items_str.split(";") if item.strip()
            ]

            # Only add to the dictionary if there are actual valid workshop IDs
            if workshop_ids:
                servers_workshopids_lists[server_name] = workshop_ids
            else:
                print(
                    f"Info: 'WorkshopItems' found but contained no valid IDs after cleaning for server '{server_name}' in {path}."
                )

        except FileNotFoundError:
            print(f"Error: File not found at '{path}'. Skipping this file.")
        except IndexError:
            # Catches issues if path.split('/') doesn't have enough parts
            print(
                f"Error: Path format unexpected for '{path}'. Could not extract username. Skipping."
            )
        except KeyError as e:
            # This would catch if config["default"] was missing, but .get() handles WorkshopItems
            print(
                f"Error: Missing expected configuration key '{e}' in {path} for server '{server_name}'. Skipping."
            )
        except Exception as e:
            # Catch any other unexpected errors during processing
            print(
                f"An unexpected error occurred while processing '{path}' for server '{server_name}': {e}. Skipping."
            )

    print("\n---")
    print(
        "All collected workshop items by server (username):", servers_workshopids_lists
    )
    print("---")
    return servers_workshopids_lists


async def servers_with_mod_update(workshop_id: str) -> list[str]:
    """Returns a list of running servers the updated mod is running on"""
    # Check for workshop_id in each servers list
    # and if its present add server to list
    paths = await server_setting_paths()
    servers = await get_servers_workshop_ids(paths)

    server_names = []
    for key, value in servers.items():
        if workshop_id in value:
            server_names.append(SERVER_NAMES[key])
    return server_names


async def combine_servers_workshop_ids() -> list:
    """Returns all workshop_ids together from running servers."""
    paths = await server_setting_paths()
    servers = await get_servers_workshop_ids(paths)
    all_servers_workshop_ids = set()
    for value in servers.values():
        if value:
            all_servers_workshop_ids.update(value)

    # Steam lib wants list, also...
    workshop_ids = list(all_servers_workshop_ids)
    print(f"Found this many workshop_ids:{len(workshop_ids)}")
    return workshop_ids


async def restart_zomboid_server(system_user: str):
    """Restarts the Project Zomboid game-server service.

    Args:
        system_user: The name of the linux user running the game server.

    """

    try:
        cmd = ["sudo", "/usr/bin/systemctl", "restart", system_user]
        process = await asyncio.create_subprocess_exec(*cmd)
        exit_code = await process.wait()
        if exit_code != 0:
            return False
    except Exception as e:
        print(f"error occurred: {e}")
        return False
    return True


def get_game_version(servername: str):
    """
    Detects the PZ version based on the Java release file.
    Example path: /home/pzserver/serverfiles/jre64/release
    """
    # Construct the dynamic path based on the servername parameter
    path = f"/home/{servername}/serverfiles/jre64/release"

    if not os.path.exists(path):
        print(f"Warning: Path not found: {path}")
        return "UNKNOWN"

    try:
        with open(path, "r") as f:
            content = f.read()

            # Build 42 uses Java 25
            if 'JAVA_VERSION="25' in content:
                return "B42"

            # Build 41 uses Java 17
            elif 'JAVA_VERSION="17' in content:
                return "B41"

    except Exception as e:
        print(f"Error reading release file for {servername}: {e}")

    return "UNKNOWN"
