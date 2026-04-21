import logging
import os
from pathlib import Path

from src.config import Config
from src.services.server import get_workshop_ids_for_server

logger = logging.getLogger(__name__)

_VEHICLE_DIRS = ("vehicles",)


class VehicleCache:
    def __init__(self):
        self._vehicles: dict[str, list[tuple[str, str]]] = {}

    def get_vehicles(self, system_user: str) -> list[tuple[str, str]]:
        return self._vehicles.get(system_user, [])

    async def scan_all_servers(self):
        import asyncio

        for server_config in Config.SERVER_DATA:
            system_user = server_config["system_user"]
            logger.info(f"Scanning vehicles for {system_user}...")
            vehicles = await asyncio.to_thread(self._scan_server, system_user)
            self._vehicles[system_user] = vehicles
            logger.info(f"Found {len(vehicles)} vehicles for {system_user}")

    def _scan_server(self, system_user: str) -> list[tuple[str, str]]:
        vehicles_dict: dict[str, str] = {}
        active_workshop_ids = get_workshop_ids_for_server(system_user)

        base_path = Path(f"/home/{system_user}/serverfiles/media/scripts")
        if base_path.exists():
            self._scan_vehicles_dir(base_path / "generated" / "vehicles", vehicles_dict)

        workshop_path = Path(
            f"/home/{system_user}/serverfiles/steamapps/workshop/content/108600"
        )
        if workshop_path.exists():
            self._scan_workshop_dir(workshop_path, vehicles_dict, active_workshop_ids)

        vehicles = sorted(vehicles_dict.items(), key=lambda x: x[0].lower())
        return vehicles

    def _scan_vehicles_dir(self, vehicles_dir: Path, vehicles_dict: dict[str, str]):
        if not vehicles_dir.exists():
            return
        for txt_file in vehicles_dir.rglob("*.txt"):
            self._parse_vehicle_file(txt_file, vehicles_dict)

    def _scan_workshop_dir(self, workshop_dir: Path, vehicles_dict: dict[str, str], active_workshop_ids: set[str]):
        for txt_file in workshop_dir.rglob("*.txt"):
            parts = txt_file.parts
            rel = txt_file.relative_to(workshop_dir)
            rel_str = str(rel)

            first_dir = rel_str.split(os.sep, 1)[0] if os.sep in rel_str else rel_str.split("/", 1)[0]
            if first_dir not in active_workshop_ids:
                continue

            if "media" not in parts:
                continue
            if "scripts" not in parts:
                continue

            in_vehicle_dir = any(
                f"{os.sep}{d}{os.sep}" in rel_str or rel_str.startswith(d + "/")
                for d in _VEHICLE_DIRS
            )
            if not in_vehicle_dir:
                continue

            self._parse_vehicle_file(txt_file, vehicles_dict)

    def _parse_vehicle_file(self, filepath: Path, vehicles_dict: dict[str, str]):
        try:
            with open(filepath, "r", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read {filepath}: {e}")
            return

        current_module = None
        depth = 0
        in_vehicle = False
        vehicle_depth = 0
        current_vehicle_name = None

        for line in content.splitlines():
            stripped = line.strip()

            if not stripped or stripped.startswith("/*") or stripped.startswith("//"):
                continue

            depth_change = stripped.count("{") - stripped.count("}")
            if depth_change != 0:
                if in_vehicle and depth + depth_change < vehicle_depth:
                    if current_module and current_vehicle_name:
                        full_id = f"{current_module}.{current_vehicle_name}"
                        if full_id not in vehicles_dict:
                            vehicles_dict[full_id] = ""
                    in_vehicle = False
                    current_vehicle_name = None
                depth += depth_change
                if depth < 0:
                    depth = 0
                continue

            if not in_vehicle:
                if stripped.startswith("module ") and depth == 0:
                    current_module = stripped[7:].strip().rstrip("{").strip()

                elif stripped.startswith("vehicle ") and depth == 1 and current_module:
                    vehicle_name = stripped[8:].strip().rstrip("{").strip()
                    if vehicle_name and " " not in vehicle_name:
                        in_vehicle = True
                        vehicle_depth = depth + 1
                        current_vehicle_name = vehicle_name


vehicle_cache = VehicleCache()
