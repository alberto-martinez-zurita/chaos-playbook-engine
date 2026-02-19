"""
Tools for interacting with the Chaos Playbook.

This module centralizes all functions related to reading from and writing to
the playbook, using the asynchronous PlaybookStorage.
"""

from typing import List, TypedDict
from ..core.playbook_storage import PlaybookStorage

class Procedure(TypedDict):
    id: str
    failure_type: str
    api: str
    recovery_strategy: str
    success_rate: float
    created_at: str


class AddScenarioResponse(TypedDict):
    message: str


# ============================================================
# Tool Functions
# ============================================================

async def get_playbook(storage: PlaybookStorage) -> List[Procedure]:
    """
    Returns all procedures from the playbook in a strictly typed structure.
    """

    procedures = await storage.load_procedures()

    normalized: List[Procedure] = []

    for p in procedures:
        normalized.append(
            {
                "id": str(p.get("id", "")),
                "failure_type": str(p.get("failure_type", "")),
                "api": str(p.get("api", "")),
                "recovery_strategy": str(p.get("recovery_strategy", "")),
                "success_rate": float(p.get("success_rate", 1.0)),
                "created_at": str(p.get("created_at", "")),
            }
        )

    return normalized


async def add_scenario_to_playbook(
    storage: PlaybookStorage,
    failure_type: str,
    api: str,
    recovery_strategy: str
) -> AddScenarioResponse:
    """
    Adds a new recovery procedure to the playbook.
    """

    procedure_id = await storage.save_procedure(
        failure_type=failure_type,
        api=api,
        recovery_strategy=recovery_strategy,
        metadata={}  # internal only, not exposed to Gemini
    )

    return {
        "message": f"Successfully added new procedure with ID: {procedure_id}"
    }
