"""Persistent cache for recently used iDotMatrix device BLE addresses.

Stores up to MAX_CACHED_DEVICES addresses in a JSON file, most recently
used first.  Corrupt or missing files are silently treated as empty.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = Path("~/.config/idotmatrix/devices.json").expanduser()
MAX_CACHED_DEVICES = 10


def load_cache(cache_path: Path = DEFAULT_CACHE_PATH) -> list[str]:
    """Read cached device addresses.  Returns [] on missing/corrupt file."""
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(data, list) and all(isinstance(a, str) for a in data):
            return data[:MAX_CACHED_DEVICES]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return []


def save_cache(
    addresses: list[str], cache_path: Path = DEFAULT_CACHE_PATH
) -> None:
    """Write addresses to the cache file, truncating to MAX_CACHED_DEVICES."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(addresses[:MAX_CACHED_DEVICES]), encoding="utf-8"
    )


def add_to_cache(
    address: str, cache_path: Path = DEFAULT_CACHE_PATH
) -> None:
    """Add *address* to the front of the cache (or move it there if present)."""
    addresses = load_cache(cache_path)
    if address in addresses:
        addresses.remove(address)
    addresses.insert(0, address)
    save_cache(addresses, cache_path)
