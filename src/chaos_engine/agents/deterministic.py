"""
DeterministicAgent - LLM-free workflow engine for parametric simulation.

Executes the same 4-step Petstore workflow as PetstoreAgent but replaces
LLM reasoning with deterministic strategy execution. Uses the real
infrastructure stack: ChaosProxy, CircuitBreakerProxy, and playbook lookup.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Final, Optional, Tuple

from chaos_engine.core.protocols import Executor
from chaos_engine.core.types import (
    ApiResponse,
    ExperimentResult,
    RetryStrategy,
    Status,
    WorkflowStep,
)


# Step definition: (result_name, playbook_tool_name, http_method, endpoint, params, json_body)
WORKFLOW_STEPS: Final[tuple[
    tuple[str, str, str, str, Optional[Dict], Optional[Dict]], ...
]] = (
    (WorkflowStep.GET_INVENTORY, WorkflowStep.GET_INVENTORY, "GET", "/store/inventory", None, None),
    (WorkflowStep.FIND_PETS, WorkflowStep.FIND_PETS, "GET", "/pet/findByStatus", {"status": "available"}, None),
    (WorkflowStep.PLACE_ORDER, WorkflowStep.PLACE_ORDER, "POST", "/store/order",
     None, {"petId": 12345, "quantity": 1, "status": "placed", "complete": False}),
    (WorkflowStep.UPDATE_PET, WorkflowStep.UPDATE_PET, "PUT", "/pet",
     None, {"id": 12345, "name": "MockPet", "status": "sold", "photoUrls": []}),
)


class DeterministicAgent:
    """
    Deterministic workflow engine that mirrors PetstoreAgent behavior
    without LLM calls. Uses real ChaosProxy + CircuitBreakerProxy + playbook.
    """

    def __init__(
        self,
        tool_executor: Executor,
        playbook_path: str,
        verbose: bool = False,
        simulate_delays: bool = False,
    ):
        self.executor = tool_executor
        self.playbook_data = self._load_playbook(playbook_path)
        self.verbose = verbose
        self.simulate_delays = simulate_delays
        self.logger = logging.getLogger("DeterministicAgent")

    @staticmethod
    def _load_playbook(path: str) -> Dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logging.getLogger("DeterministicAgent").warning("Error loading playbook %s", path, exc_info=True)
            return {}

    async def run(self) -> ExperimentResult:
        """Execute the 4-step workflow. Returns result compatible with ABTestRunner."""
        start_time = time.time()
        steps_completed: list[str] = []
        failed_at: str | None = None
        total_retries = 0
        total_simulated_delay = 0.0

        for step_name, tool_name, method, endpoint, params, json_body in WORKFLOW_STEPS:
            result, retries, simulated_delay = await self._execute_step(
                tool_name, method, endpoint, params, json_body
            )
            total_retries += retries
            total_simulated_delay += simulated_delay

            if result.get("status") == Status.SUCCESS:
                steps_completed.append(step_name)
            else:
                failed_at = step_name
                break

        duration_ms = (time.time() - start_time) * 1000
        status = Status.SUCCESS if failed_at is None else Status.FAILURE

        return ExperimentResult(
            status=status,
            steps_completed=steps_completed,
            failed_at=failed_at,
            duration_ms=duration_ms,
            retries=total_retries,
            simulated_delay_s=round(total_simulated_delay, 3),
            outcome=status,
            agent_type="",
        )

    async def _execute_step(
        self, tool_name: str, method: str, endpoint: str,
        params: Optional[Dict], json_body: Optional[Dict],
    ) -> Tuple[Dict, int, float]:
        """Execute a single step with playbook-driven recovery. Returns (result, retries, simulated_delay)."""

        result = await self.executor.send_request(method, endpoint, params, json_body)

        if result.get("status") == Status.SUCCESS:
            return result, 0, 0.0

        # Error path — consult playbook
        error_code = str(result.get("code", 500))
        strategy_entry = self._resolve_strategy(tool_name, error_code)
        strategy = strategy_entry.get("strategy", RetryStrategy.FAIL_FAST)
        config = strategy_entry.get("config", {})

        if self.verbose:
            self.logger.info(
                "  [%s] Error %s -> strategy: %s", tool_name, error_code, strategy
            )

        if strategy in (RetryStrategy.FAIL_FAST, RetryStrategy.ESCALATE_TO_HUMAN):
            return result, 0, 0.0

        return await self._retry_with_strategy(
            strategy, config, method, endpoint, params, json_body
        )

    def _resolve_strategy(self, tool_name: str, error_code: str) -> Dict[str, Any]:
        """Lookup playbook by tool_name + error_code, fallback to default."""
        tool_config = self.playbook_data.get(tool_name, {})
        entry = tool_config.get(error_code)
        if entry:
            return entry
        default = self.playbook_data.get("default")
        if default:
            return default
        return {"strategy": RetryStrategy.FAIL_FAST, "config": {}}

    async def _retry_with_strategy(
        self, strategy: str, config: Dict,
        method: str, endpoint: str,
        params: Optional[Dict], json_body: Optional[Dict],
    ) -> Tuple[Dict, int, float]:
        """Execute retry strategy. Returns (final_result, retries_used, simulated_delay)."""

        max_retries = config.get("max_retries", 3)
        total_delay = 0.0

        for attempt in range(1, max_retries + 1):
            delay = self._calculate_delay(strategy, config, attempt)
            jittered = self.executor.calculate_jittered_backoff(delay)
            total_delay += jittered

            if self.simulate_delays:
                await asyncio.sleep(jittered)

            result = await self.executor.send_request(method, endpoint, params, json_body)

            if result.get("status") == Status.SUCCESS:
                return result, attempt, total_delay

        # All retries exhausted
        return result, max_retries, total_delay

    @staticmethod
    def _calculate_delay(strategy: str, config: Dict, attempt: int) -> float:
        """Calculate base delay before jitter, based on strategy type."""
        if strategy == RetryStrategy.RETRY_LINEAR:
            return config.get("delay", 1.0) * attempt

        if strategy == RetryStrategy.WAIT_AND_RETRY:
            return config.get("wait_seconds", 5.0)

        if strategy == RetryStrategy.RETRY_EXPONENTIAL:
            base = config.get("base_delay", 1.0)
            return base * (2 ** (attempt - 1))

        return 1.0
