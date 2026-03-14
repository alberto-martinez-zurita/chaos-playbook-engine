"""Shared type definitions for the Chaos Playbook Engine."""
from __future__ import annotations

from enum import StrEnum
from typing import Any, TypedDict


# ---------------------------------------------------------------------------
# A.9 — Domain enumerations replacing magic strings
# ---------------------------------------------------------------------------

class Status(StrEnum):
    """Outcome status for API responses and experiment results."""
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"


class WorkflowStep(StrEnum):
    """Canonical names for the 4-step Petstore workflow."""
    GET_INVENTORY = "get_inventory"
    FIND_PETS = "find_pets_by_status"
    PLACE_ORDER = "place_order"
    UPDATE_PET = "update_pet_status"


class RetryStrategy(StrEnum):
    """Playbook retry strategies supported by DeterministicAgent."""
    FAIL_FAST = "fail_fast"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    RETRY_LINEAR = "retry_linear_backoff"
    RETRY_EXPONENTIAL = "retry_exponential_backoff"
    WAIT_AND_RETRY = "wait_and_retry"


# ---------------------------------------------------------------------------
# A.8 — Typed dictionaries for public return types
# ---------------------------------------------------------------------------

class ApiResponse(TypedDict, total=False):
    """Return type for ChaosProxy.send_request and CircuitBreakerProxy.send_request."""
    status: str
    code: int
    data: dict[str, Any] | None
    message: str | None


class ExperimentResult(TypedDict, total=False):
    """Return type for DeterministicAgent.run() and ABTestRunner.run_experiment()."""
    status: str
    steps_completed: list[str]
    failed_at: str | None
    duration_ms: float
    retries: int
    simulated_delay_s: float
    outcome: str
    agent_type: str
    # Added by ParametricABTestRunner
    experiment_id: str
    failure_rate: float
    seed: int
    inconsistencies_count: int
