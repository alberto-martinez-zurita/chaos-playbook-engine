"""
Chaos Playbook Storage Module.

Provides JSON-based storage for chaos recovery strategy matrix.
Thread-safe operations with asyncio.Lock.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional


class PlaybookStorage:
    """
    JSON-based storage for chaos recovery strategy matrix.

    Schema:
    {
        "get_inventory": {
            "500": {
                "strategy": "retry_exponential_backoff",
                "reasoning": "Server error",
                "config": {"base_delay": 1.0, "max_retries": 3}
            }
        },
        "default": {
            "strategy": "escalate_to_human",
            "reasoning": "Unknown scenario",
            "config": {}
        }
    }
    """

    def __init__(self, file_path: str = "data/chaos_playbook.json"):
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        self._ensure_storage_exists()

    def _ensure_storage_exists(self):
        """Ensure data directory and file exist."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            with open(self.file_path, "w") as f:
                json.dump({}, f, indent=2)

     
    async def _read_playbook(self) -> dict:
        async with self._lock:
            if not self.file_path.exists() or self.file_path.stat().st_size == 0:
            # initialize with empty matrix
                return {}
            try:
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
            # corrupted file? reset to empty matrix
                return {}        

    async def _write_playbook(self, data: Dict[str, Any]):
        async with self._lock:
            with open(self.file_path, "w") as f:
                json.dump(data, f, indent=2)

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    async def load_playbook(self) -> Dict[str, Any]:
        """Return full strategy matrix."""
        return await self._read_playbook()

    async def save_playbook(self, playbook: Dict[str, Any]) -> None:
        """Replace entire playbook."""
        await self._write_playbook(playbook)

    async def add_or_update_strategy(
        self,
        api: str,
        status_code: str,
        strategy: str,
        reasoning: str = "",
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add or update strategy rule for api + status_code."""

        if config is None:
            config = {}

        playbook = await self._read_playbook()

        if api not in playbook:
            playbook[api] = {}

        playbook[api][str(status_code)] = {
            "strategy": strategy,
            "reasoning": reasoning,
            "config": config
        }

        await self._write_playbook(playbook)

    async def remove_strategy(
        self,
        api: str,
        status_code: str
    ) -> None:
        """Remove a strategy rule."""

        playbook = await self._read_playbook()

        if api in playbook and str(status_code) in playbook[api]:
            del playbook[api][str(status_code)]

        await self._write_playbook(playbook)

    async def set_default_strategy(
        self,
        strategy: str,
        reasoning: str = "",
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Set default fallback strategy."""

        if config is None:
            config = {}

        playbook = await self._read_playbook()

        playbook["default"] = {
            "strategy": strategy,
            "reasoning": reasoning,
            "config": config
        }

        await self._write_playbook(playbook)

    async def resolve_strategy(
        self,
        api: str,
        status_code: str
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve strategy for given api + status_code.
        Falls back to default if not found.
        """

        playbook = await self._read_playbook()

        api_rules = playbook.get(api, {})
        if str(status_code) in api_rules:
            return api_rules[str(status_code)]

        return playbook.get("default")