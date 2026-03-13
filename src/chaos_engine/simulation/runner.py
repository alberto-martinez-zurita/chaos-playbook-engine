"""
ABTestRunner - Orchestrator for Parametric Simulation using DeterministicAgent.

Refactored to use the real infrastructure stack (ChaosProxy, CircuitBreakerProxy,
playbook lookup) instead of simulated API functions.
"""

import time
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from chaos_engine.agents.deterministic import DeterministicAgent
from chaos_engine.chaos.proxy import ChaosProxy
from chaos_engine.core.resilience import CircuitBreakerProxy

# Default playbook paths (relative to project root)
_DEFAULT_BASELINE = str(Path("assets/playbooks/baseline.json"))
_DEFAULT_TRAINING = str(Path("assets/playbooks/training.json"))


class ABTestRunner:
    def __init__(
        self,
        playbook_baseline_path: str = _DEFAULT_BASELINE,
        playbook_training_path: str = _DEFAULT_TRAINING,
        simulate_delays: bool = False,
        logger: Optional[logging.Logger] = None,
    ):
        self.playbook_baseline_path = playbook_baseline_path
        self.playbook_training_path = playbook_training_path
        self.simulate_delays = simulate_delays
        self.logger = logger or logging.getLogger(__name__)

    async def run_experiment(self, agent_type: str, failure_rate: float, seed: int) -> Dict[str, Any]:
        """Run a single experiment with fresh ChaosProxy + CircuitBreaker + DeterministicAgent."""

        # 1. Create fresh infrastructure per experiment (no state leakage)
        chaos_proxy = ChaosProxy(
            failure_rate=failure_rate,
            seed=seed,
            mock_mode=True,
            verbose=False,
        )
        circuit_breaker = CircuitBreakerProxy(
            wrapped_executor=chaos_proxy,
            failure_threshold=3,
            cooldown_seconds=30,
        )

        # 2. Select playbook based on agent type
        playbook_path = (
            self.playbook_training_path
            if agent_type == "playbook"
            else self.playbook_baseline_path
        )

        # 3. Create and run deterministic agent
        agent = DeterministicAgent(
            tool_executor=circuit_breaker,
            playbook_path=playbook_path,
            simulate_delays=self.simulate_delays,
        )

        result = await agent.run()
        result["agent_type"] = agent_type

        return result
