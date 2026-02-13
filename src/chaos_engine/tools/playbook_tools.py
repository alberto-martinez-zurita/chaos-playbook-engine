"""
Tools for interacting with the Chaos Playbook.

This module centralizes all functions related to reading from and writing to
the playbook, using the asynchronous PlaybookStorage.
"""
from typing import Any, Dict, List, Optional
from ..core.playbook_storage import PlaybookStorage

async def get_playbook(storage: PlaybookStorage) -> List[Dict[str, Any]]:
    """Returns all procedures from the playbook."""
    return await storage.load_procedures()

async def add_scenario_to_playbook(
    storage: PlaybookStorage,
    failure_type: str,
    api: str,
    recovery_strategy: str,
    metadata: Optional[Dict] = None
) -> str:
    """
    Adds a new recovery procedure to the playbook and returns its ID.
    """
    procedure_id = await storage.save_procedure(
        failure_type=failure_type,
        api=api,
        recovery_strategy=recovery_strategy,
        metadata=metadata or {}
    )
    return f"Successfully added new procedure with ID: {procedure_id}"