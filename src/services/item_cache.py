import json
import logging
import os
import re
from pathlib import Path

from src.config import Config, DATA_DIR

logger = logging.getLogger(__name__)

CACHE_FILE = DATA_DIR / "items_cache.json"
CACHE_VERSION = 2

_LUA_ITEMNAME_RE = re.compile(r'ItemName_(\S+)\s*=\s*"([^"]*)"')
_JSON_PAIR_RE = re.compile(r'"([^"]+)"\s*:\s*"([^"]*)"')


class ItemCache:
    def __init__(self):
        self._items: dict[str, list[tuple[str, str]]] = {}

    def get_items(self, system_user: str) -> list[tuple[str, str]]:
        return self._items.get(system_user, [])

    def load_from_disk(self) -> bool:
        if not CACHE_FILE.exists():
            return False
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
            if data.get("version") != CACHE_VERSION:
                logger.info("Item cache version mismatch, re-scanning")
                return False
            self._items = {}
            for user, items in data.get("servers", {}).items():
                self._items[user] = [(i[0], i[1]) for i in items]
            total = sum(len(v) for v in self._items.values())
            logger.info(f"Loaded {total} items from cache for {len(self._items)} servers")
            return True
        except Exception as e:
            logger.error(f"Failed to load item cache: {e}")
            return False

    def save_to_disk(self):
        try:
            data = {
                "version": CACHE_VERSION,
                "servers": {
                    user: [[i[0], i[1]] for i in items]
                    for user, items in self._items.items()
                },
            }
            with open(CACHE_FILE, "w") as f:
                json.dump(data, f)
            total = sum(len(v) for v in self._items.values())
            logger.info(f"Saved {total} items to cache for {len(self._items)} servers")
        except Exception as e:
            logger.error(f"Failed to save item cache: {e}")

    async def scan_all_servers(self):
        import asyncio

        for server_config in Config.SERVER_DATA:
            system_user = server_config["system_user"]
            logger.info(f"Scanning items for {system_user}...")
            items = await asyncio.to_thread(self._scan_server, system_user)
            self._items[system_user] = items
            logger.info(f"Found {len(items)} items for {system_user}")

        self.save_to_disk()

    def _scan_server(self, system_user: str) -> list[tuple[str, str]]:
        items_dict: dict[str, str] = {}

        base_path = Path(f"/home/{system_user}/serverfiles/media/scripts")
        if base_path.exists():
            self._scan_items_dir(base_path / "generated" / "items", items_dict)

        workshop_path = Path(
            f"/home/{system_user}/serverfiles/steamapps/workshop/content/108600"
        )
        if workshop_path.exists():
            self._scan_workshop_dir(workshop_path, items_dict)

        translations: dict[str, str] = {}
        self._load_base_translations(system_user, translations)
        if workshop_path.exists():
            self._load_mod_translations(workshop_path, translations)

        for item_id, display_name in items_dict.items():
            if not display_name and item_id in translations:
                items_dict[item_id] = translations[item_id]

        for item_id, display_name in translations.items():
            if item_id not in items_dict:
                items_dict[item_id] = display_name

        items = sorted(items_dict.items(), key=lambda x: x[0].lower())
        return items

    def _scan_items_dir(self, items_dir: Path, items_dict: dict[str, str]):
        if not items_dir.exists():
            return
        for txt_file in items_dir.rglob("*.txt"):
            self._parse_script_file(txt_file, items_dict)

    def _scan_workshop_dir(self, workshop_dir: Path, items_dict: dict[str, str]):
        for txt_file in workshop_dir.rglob("*.txt"):
            parts = txt_file.parts
            rel = txt_file.relative_to(workshop_dir)
            rel_str = str(rel)

            skip_dirs = ("vehicles", "entities")
            if any(f"{os.sep}{d}{os.sep}" in rel_str or rel_str.startswith(d + "/") for d in skip_dirs):
                continue

            if "media" not in parts:
                continue
            if "scripts" not in parts:
                continue

            self._parse_script_file(txt_file, items_dict)

    def _parse_script_file(self, filepath: Path, items_dict: dict[str, str]):
        try:
            with open(filepath, "r", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read {filepath}: {e}")
            return

        current_module = None
        depth = 0
        in_item = False
        item_depth = 0
        current_item_name = None
        current_display_name = None

        for line in content.splitlines():
            stripped = line.strip()

            if not stripped or stripped.startswith("/*") or stripped.startswith("//"):
                continue

            depth_change = stripped.count("{") - stripped.count("}")
            if depth_change != 0:
                if in_item and depth + depth_change < item_depth:
                    if current_module and current_item_name:
                        full_id = f"{current_module}.{current_item_name}"
                        if full_id not in items_dict:
                            items_dict[full_id] = current_display_name or ""
                    in_item = False
                    current_item_name = None
                    current_display_name = None
                depth += depth_change
                if depth < 0:
                    depth = 0
                continue

            if not in_item:
                if stripped.startswith("module ") and depth == 0:
                    current_module = stripped[7:].strip().rstrip("{").strip()

                elif stripped.startswith("item ") and depth == 1 and current_module:
                    item_name = stripped[5:].strip().rstrip("{").strip()
                    if item_name and " " not in item_name:
                        in_item = True
                        item_depth = depth + 1
                        current_item_name = item_name
                        current_display_name = None
            else:
                if stripped.startswith("DisplayName"):
                    idx = stripped.find("=")
                    if idx != -1:
                        val = stripped[idx + 1:].strip().rstrip(",").strip()
                        if val and current_display_name is None:
                            current_display_name = val

    def _load_base_translations(self, system_user: str, translations: dict[str, str]):
        json_path = Path(
            f"/home/{system_user}/serverfiles/media/lua/shared/Translate/EN/ItemName.json"
        )
        if not json_path.exists():
            return
        try:
            with open(json_path, "r", errors="ignore") as f:
                data = json.load(f)
            for item_id, name in data.items():
                if name and item_id not in translations:
                    translations[item_id] = name
        except Exception as e:
            logger.warning(f"Failed to load base translations for {system_user}: {e}")

    def _load_mod_translations(self, workshop_dir: Path, translations: dict[str, str]):
        for trans_file in workshop_dir.rglob("Translate/EN/ItemName*"):
            if trans_file.suffix == ".json":
                self._parse_json_translation(trans_file, translations)
            elif trans_file.suffix == ".txt":
                self._parse_lua_translation(trans_file, translations)

    def _parse_json_translation(self, filepath: Path, translations: dict[str, str]):
        try:
            with open(filepath, "r", errors="ignore") as f:
                data = json.load(f)
            for item_id, name in data.items():
                if name and item_id not in translations:
                    translations[item_id] = name
            return
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.warning(f"Failed to parse {filepath}: {e}")
            return

        try:
            with open(filepath, "r", errors="ignore") as f:
                content = f.read()
            for m in _JSON_PAIR_RE.finditer(content):
                item_id, name = m.group(1), m.group(2)
                if name and item_id not in translations:
                    translations[item_id] = name
        except Exception as e:
            logger.warning(f"Failed to regex-parse {filepath}: {e}")

    def _parse_lua_translation(self, filepath: Path, translations: dict[str, str]):
        try:
            with open(filepath, "r", errors="ignore") as f:
                for line in f:
                    m = _LUA_ITEMNAME_RE.search(line)
                    if m:
                        item_id = m.group(1)
                        name = m.group(2)
                        if name and item_id not in translations:
                            translations[item_id] = name
        except Exception as e:
            logger.warning(f"Failed to parse {filepath}: {e}")


item_cache = ItemCache()
