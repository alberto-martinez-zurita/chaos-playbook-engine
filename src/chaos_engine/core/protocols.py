"""
Unified Protocol definitions for the Chaos Playbook Engine.

Single source of truth for all interface contracts (DRY).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class Executor(Protocol):
    """Contract for HTTP request executors.

    Satisfied by ChaosProxy, CircuitBreakerProxy, HttpExecutor, and test doubles.
    """

    async def send_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]: ...

    def calculate_jittered_backoff(self, seconds: float) -> float: ...


@runtime_checkable
class AgentRunner(Protocol):
    """Contract for agent execution backends.

    Abstracts away the specific LLM framework (Google ADK, LangChain, etc.)
    so domain agents don't import framework types directly (A.29).

    Implementations:
    - ``Adk InMemoryRunner`` adapter (wraps ``google.adk.runners.InMemoryRunner``)
    - Test doubles for unit testing without LLM calls
    """

    async def run(self, prompt: str) -> str:
        """Execute the agent with the given prompt and return the text output."""
        ...


@runtime_checkable
class WorkflowAgent(Protocol):
    """Contract for workflow agents that execute multi-step processes.

    Satisfied by DeterministicAgent and PetstoreAgent.
    """

    async def run(self) -> Dict[str, Any]:
        """Execute the agent's workflow and return an ExperimentResult-compatible dict."""
        ...
