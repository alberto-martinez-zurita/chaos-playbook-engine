"""Tests for PlaybookStorage — JSON strategy matrix with hot-reload."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from chaos_engine.core.playbook_storage import PlaybookStorage


# --- FIXTURES ---

@pytest.fixture
def temp_storage_file(tmp_path):
    """Create a temporary path for the playbook JSON file."""
    d = tmp_path / "data"
    d.mkdir()
    return str(d / "test_chaos_playbook.json")


# --- TESTS ---

@pytest.mark.asyncio
async def test_storage_initialization_creates_file(temp_storage_file):
    """Verify that if the file doesn't exist, an empty JSON object is created."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    assert Path(temp_storage_file).exists()

    with open(temp_storage_file, "r") as f:
        data = json.load(f)
        assert data == {}


@pytest.mark.asyncio
async def test_add_and_resolve_strategy(temp_storage_file):
    """Verify adding a strategy and resolving it by api + status_code."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    await storage.add_or_update_strategy(
        api="get_inventory",
        status_code="500",
        strategy="retry_exponential_backoff",
        reasoning="Server error, safe to retry",
        config={"base_delay": 1.0, "max_retries": 3},
    )

    resolved = await storage.resolve_strategy("get_inventory", "500")
    assert resolved is not None
    assert resolved["strategy"] == "retry_exponential_backoff"
    assert resolved["config"]["base_delay"] == 1.0


@pytest.mark.asyncio
async def test_resolve_falls_back_to_default(temp_storage_file):
    """Verify fallback to default strategy when specific rule not found."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    await storage.set_default_strategy(
        strategy="escalate_to_human",
        reasoning="Unknown scenario",
    )

    resolved = await storage.resolve_strategy("unknown_api", "999")
    assert resolved is not None
    assert resolved["strategy"] == "escalate_to_human"


@pytest.mark.asyncio
async def test_resolve_returns_none_when_no_match(temp_storage_file):
    """Verify None returned when no strategy matches and no default set."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    resolved = await storage.resolve_strategy("unknown_api", "500")
    assert resolved is None


@pytest.mark.asyncio
async def test_remove_strategy(temp_storage_file):
    """Verify strategy removal."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    await storage.add_or_update_strategy(
        api="place_order", status_code="429",
        strategy="wait_and_retry", config={"wait_seconds": 5},
    )
    await storage.remove_strategy("place_order", "429")

    resolved = await storage.resolve_strategy("place_order", "429")
    assert resolved is None


@pytest.mark.asyncio
async def test_save_and_load_full_playbook(temp_storage_file):
    """Verify full playbook save/load round trip."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    playbook = {
        "get_inventory": {
            "500": {"strategy": "retry_exponential_backoff", "config": {"base_delay": 1.0}},
        },
        "default": {"strategy": "fail_fast", "config": {}},
    }

    await storage.save_playbook(playbook)
    loaded = await storage.load_playbook()

    assert loaded["get_inventory"]["500"]["strategy"] == "retry_exponential_backoff"
    assert loaded["default"]["strategy"] == "fail_fast"


@pytest.mark.asyncio
async def test_hot_reload_detects_file_change(temp_storage_file):
    """Verify get_cached_playbook picks up external file changes."""
    storage = PlaybookStorage(file_path=temp_storage_file)

    # Prime the cache
    await storage.get_cached_playbook()

    # External write simulating another process updating the file
    new_data = {"external_update": {"200": {"strategy": "fail_fast"}}}
    with open(temp_storage_file, "w") as f:
        json.dump(new_data, f)

    # Force mtime change detection
    import os
    import time
    # Touch file to ensure mtime differs
    os.utime(temp_storage_file, (time.time() + 1, time.time() + 1))

    cached = await storage.get_cached_playbook()
    assert "external_update" in cached
