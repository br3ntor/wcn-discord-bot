import asyncio
import configparser

from config import LOCAL_SERVER_IP, SERVER_DATA


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


# This was going to be for checking before/while creating choices for discord command
# But I don't know how or if I even should do such a thing
# async def local_running_servers() -> list[str]:
#     """Returns a list of running servers on the local machine"""
#
#     # Get names of local servers
#     local_servers = [
#         server["name"] for server in SERVER_DATA if server["ip"] == LOCAL_SERVER_IP
#     ]
#
#     # Check and return only running servers
#     running_servers = [
#         server for server in local_servers if await server_isrunning(server)
#     ]
#     return running_servers


async def server_setting_paths() -> list:
    """Return list of paths to running servers settings files"""
    server_files = []
    servers_with_gists = [server["name"] for server in SERVER_DATA if server["gists"]]
    for server_name in servers_with_gists:
        if await server_isrunning(server_name):
            server_files.append(f"/home/{server_name}/Zomboid/Server/pzserver.ini")
    return server_files


async def get_servers_workshop_ids(
    file_paths: list[str],
) -> dict[str, list[str]]:
    """Returns running server names with their workshop ids"""

    # Well use a dictionary to map running servers to thier workshop_ids list
    servers_workshopids_lists = {}

    config = configparser.ConfigParser()
    for path in file_paths:
        # This sets proper syntax to parse file with ConfigParser
        with open(path) as stream:
            config.read_string("[default]\n" + stream.read())
        servers_workshopids_lists.update(
            {path.split("/")[2]: config["default"]["WorkshopItems"].split(";")}
        )
    return servers_workshopids_lists


async def servers_with_mod_update(workshop_id: str) -> list:
    """Returns a list of running servers the updated mod is running on"""
    # Check for workshop_id in each servers list
    # and if its present add server to list
    paths = await server_setting_paths()
    servers = await get_servers_workshop_ids(paths)

    server_names = []
    for key, value in servers.items():
        if workshop_id in value:
            server_names.append(key)
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
