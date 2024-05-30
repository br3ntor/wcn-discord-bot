import asyncio
import configparser

from config import SERVERNAMES


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

        # I don't think this is needed but doesn't hurt either
        # await process.wait()
    except asyncio.SubprocessError as e:
        # I got an error once about asyncio no having a SubprocessError attribute
        # I'm not sure if this is correct
        print(f"Subprocess error occurred: {e}")

    out, err = output.decode(), error.decode()

    if err:
        print(err)

    for line in out.splitlines():
        if "ProjectZomboid64" in line:
            print(f"{server} is running:\n{line}" if out else f"{server} is stopped")
            return True

    return False


async def running_servers_settings_paths():
    """Return list of paths to running servers settings files"""
    server_files = []
    for server_name in SERVERNAMES:
        if await server_isrunning(server_name):
            server_files.append(f"/home/{server_name}/Zomboid/Server/pzserver.ini")
    return server_files


async def servers_with_mod_update(workshop_id: str) -> list:
    """Returns a list of running servers the updated mod is running on"""
    # Check for workshop_id in each servers list
    # and if its present add server to list
    servers_and_mods = await get_servers_and_workshop_ids()
    server_names = []
    for key, value in servers_and_mods.items():
        if workshop_id in value:
            server_names.append(key.split("/")[2])
    return server_names


async def get_all_workshop_ids() -> list:
    """Returns one list of mod workshop ids for all running servers."""
    servers = await get_servers_and_workshop_ids()
    all_servers_workshop_ids = set()
    for value in servers.values():
        all_servers_workshop_ids.update(value)
    # Steam lib wants list, also...
    # The filter is to remove empty string(s) in the list that
    # are present when the above code encounters empty WorkshopItems in file
    workshop_ids = list(filter(None, all_servers_workshop_ids))
    print(f"Found this many workshop_ids:{len(workshop_ids)}")
    return workshop_ids


async def get_servers_and_workshop_ids() -> dict:
    """Returns running servers and their workshop ids"""
    server_files = await running_servers_settings_paths()
    config = configparser.ConfigParser()
    # Well use a dictionary to map running servers to thier workshop_ids list
    servers_workshopids_lists = {}
    for file in server_files:
        # This sets proper syntax to parse file with ConfigParser
        with open(file) as stream:
            config.read_string("[default]\n" + stream.read())
        servers_workshopids_lists.update(
            {file: config["default"]["WorkshopItems"].split(";")}
        )
    return servers_workshopids_lists
