"""
Unified Protocol definitions for the Chaos Playbook Engine.

Single source of truth for all interface contracts (DRY).
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class Executor(Protocol):
    """Contract for HTTP request executors.

    Satisfied by ChaosProxy, CircuitBreakerProxy, and any test doubles.
    """

    async def send_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]: ...

    def calculate_jittered_backoff(self, seconds: float) -> float: ...
