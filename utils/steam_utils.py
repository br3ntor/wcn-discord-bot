import os
import configparser
from steam.webapi import WebAPI


STEAM_KEY = os.getenv("STEAM_WEBAPI")


def get_mod_ids() -> list:
    """Returns a list of mod workshop ids for the server."""

    server_file = "/home/pzserver/Zomboid/Server/pzserver.ini"
    # server_file = "/home/pzserver/Zomboid/Server/fakeserver.ini"
    config = configparser.ConfigParser()

    # This seems to add the first line of the stream
    # to a header for an ini file, because the file
    # we are working with is not a proper ini file
    with open(server_file) as stream:
        config.read_string("[default]\n" + stream.read())

    workshop_ids = config["default"]["WorkshopItems"].split(";")
    print(f"Found this many workshopids: {len(workshop_ids)}")
    return workshop_ids


def get_mod_data(workshop_ids: list) -> list:
    """Calls steam api to get mod data."""
    api = WebAPI(STEAM_KEY)

    item_count = len(workshop_ids)

    workshop_items = api.ISteamRemoteStorage.GetPublishedFileDetails(
        itemcount=item_count, publishedfileids=workshop_ids
    )

    items = workshop_items["response"]["publishedfiledetails"]
    print(f"Found this many workshop_items: {len(items)}")
    return workshop_items
