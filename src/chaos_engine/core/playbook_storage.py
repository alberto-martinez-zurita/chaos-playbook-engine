"""
Chaos Playbook Storage Module.

Provides JSON-based storage for chaos recovery procedures.
Thread-safe operations with asyncio.Lock.

Location: src/chaos_playbook_engine/data/playbook_storage.py
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class PlaybookStorage:
    """
    JSON-based storage for chaos recovery procedures.

    Schema:
    {
        "procedures": [
            {
                "id": "PROC-001",
                "failure_type": "timeout",
                "api": "inventory",
                "recovery_strategy": "retry 3x with exponential backoff",
                "success_rate": 0.85,
                "created_at": "2025-11-22T15:00:00Z",
                "metadata": {...}
            }
        ]
    }
    """

    def __init__(self, file_path: str = "data/chaos_playbook.json"):
        """
        Initialize storage with file path.
        
        Args:
            file_path: Path to JSON storage file
        """
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        self._ensure_storage_exists()

    def _ensure_storage_exists(self):
        """Ensure data directory and file exist."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            initial_data = {"procedures": []}
            with open(self.file_path, 'w') as f:
                json.dump(initial_data, f, indent=2)

    async def _read_playbook(self) -> Dict[str, Any]:
        """Read playbook from disk (thread-safe)."""
        async with self._lock:
            with open(self.file_path, 'r') as f:
                return json.load(f)

    async def _write_playbook(self, data: Dict[str, Any]):
        """Write playbook to disk (thread-safe)."""
        async with self._lock:
            with open(self.file_path, 'w') as f:
                json.dump(data, f, indent=2)

    def _generate_procedure_id(self, existing_procedures: List[Dict]) -> str:
        """Generate unique procedure ID like 'PROC-001'."""
        if not existing_procedures:
            return "PROC-001"
        max_num = 0
        for proc in existing_procedures:
            proc_id = proc.get("id", "PROC-000")
            try:
                num = int(proc_id.split("-")[1])
                max_num = max(max_num, num)
            except (IndexError, ValueError):
                continue
        return f"PROC-{max_num + 1:03d}"

    def _validate_inputs(
        self,
        failure_type: str,
        api: str,
        success_rate: float
    ):
        """Validate inputs. Only success_rate is restricted now."""
        if not 0.0 <= success_rate <= 1.0:
            raise ValueError(
                f"Invalid success_rate: {success_rate}. Must be between 0.0 and 1.0"
            )

    async def save_procedure(
        self,
        failure_type: str,
        api: str,
        recovery_strategy: str,
        success_rate: float = 1.0,
        metadata: Optional[Dict] = None
    ) -> str:
        """Save recovery procedure to Playbook."""
        # Validate inputs
        self._validate_inputs(failure_type, api, success_rate)

        # Read current playbook
        playbook = await self._read_playbook()
        procedures = playbook.get("procedures", [])

        # Generate unique ID
        procedure_id = self._generate_procedure_id(procedures)

        # Create procedure entry
        procedure = {
            "id": procedure_id,
            "failure_type": failure_type,
            "api": api,
            "recovery_strategy": recovery_strategy,
            "success_rate": success_rate,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "metadata": metadata or {}
        }

        # Add to playbook
        procedures.append(procedure)
        playbook["procedures"] = procedures

        # Write back to disk
        await self._write_playbook(playbook)

        return procedure_id

    async def load_procedures(
        self,
        failure_type: Optional[str] = None,
        api: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Load procedures from Playbook with optional filtering."""
        playbook = await self._read_playbook()
        procedures = playbook.get("procedures", [])
        if failure_type:
            procedures = [p for p in procedures if p.get("failure_type") == failure_type]
        if api:
            procedures = [p for p in procedures if p.get("api") == api]
        return procedures

    async def get_best_procedure(
        self,
        failure_type: str,
        api: str
    ) -> Optional[Dict[str, Any]]:
        """Get best procedure (highest success_rate) for given failure_type and API."""
        procedures = await self.load_procedures(failure_type=failure_type, api=api)
        if not procedures:
            return None
        return max(procedures, key=lambda p: p.get("success_rate", 0.0))
