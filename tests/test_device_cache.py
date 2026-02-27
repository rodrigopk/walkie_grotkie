from __future__ import annotations

from pathlib import Path

from idotmatrix_upload.device_cache import (
    MAX_CACHED_DEVICES,
    add_to_cache,
    load_cache,
    save_cache,
)


class TestLoadCache:
    def test_load_empty_cache(self, tmp_path: Path):
        missing = tmp_path / "nope" / "devices.json"
        assert load_cache(missing) == []

    def test_load_corrupt_cache(self, tmp_path: Path):
        bad = tmp_path / "devices.json"
        bad.write_text("NOT JSON!!!", encoding="utf-8")
        assert load_cache(bad) == []

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        cache_file = tmp_path / "devices.json"
        addrs = ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:03"]
        save_cache(addrs, cache_file)
        assert load_cache(cache_file) == addrs

    def test_max_cache_size(self, tmp_path: Path):
        cache_file = tmp_path / "devices.json"
        addrs = [f"AA:BB:CC:DD:EE:{i:02X}" for i in range(12)]
        save_cache(addrs, cache_file)
        loaded = load_cache(cache_file)
        assert len(loaded) == MAX_CACHED_DEVICES
        assert loaded == addrs[:MAX_CACHED_DEVICES]


class TestAddToCache:
    def test_add_new_address(self, tmp_path: Path):
        cache_file = tmp_path / "devices.json"
        save_cache(["BB:BB:BB:BB:BB:BB"], cache_file)
        add_to_cache("AA:AA:AA:AA:AA:AA", cache_file)
        loaded = load_cache(cache_file)
        assert loaded[0] == "AA:AA:AA:AA:AA:AA"
        assert loaded[1] == "BB:BB:BB:BB:BB:BB"

    def test_add_existing_moves_to_front(self, tmp_path: Path):
        cache_file = tmp_path / "devices.json"
        save_cache(["AA:AA:AA:AA:AA:AA", "BB:BB:BB:BB:BB:BB", "CC:CC:CC:CC:CC:CC"], cache_file)
        add_to_cache("CC:CC:CC:CC:CC:CC", cache_file)
        loaded = load_cache(cache_file)
        assert loaded[0] == "CC:CC:CC:CC:CC:CC"
        assert len(loaded) == 3

    def test_cache_creates_parent_dirs(self, tmp_path: Path):
        cache_file = tmp_path / "deep" / "nested" / "devices.json"
        add_to_cache("AA:BB:CC:DD:EE:FF", cache_file)
        assert cache_file.exists()
        assert load_cache(cache_file) == ["AA:BB:CC:DD:EE:FF"]
