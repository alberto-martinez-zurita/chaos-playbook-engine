"""
ParametricABTestRunner - Orchestrator for multi-rate experiments.
Updated with DEBUGGING for Inconsistency Calculation.
REFACTORED: Streaming/Generator pattern for GreenOps compliance.
EXTENDED: Support for N agent types via AgentConfig.
"""
from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from chaos_engine.agents.deterministic import DeterministicAgent
from chaos_engine.chaos.proxy import ChaosProxy
from chaos_engine.core.resilience import CircuitBreakerProxy
from chaos_engine.core.types import Status, WorkflowStep

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for a single agent type in parametric experiments."""
    name: str          # e.g. "baseline", "aggressive", "conservative"
    playbook_path: str  # path to playbook JSON


class _StreamingAggregator:
    """Online aggregator using Welford's algorithm for mean and variance.

    Processes one result at a time — O(1) memory per rate/agent_type bucket.
    Replaces the old ``all_results_buffer`` list that required O(N) memory.
    """

    def __init__(self, agent_names: List[str]) -> None:
        # key: (failure_rate, agent_type) -> stats accumulator
        self._buckets: Dict[tuple[float, str], Dict[str, Any]] = {}
        self._agent_names = agent_names

    def _ensure_bucket(self, key: tuple[float, str]) -> Dict[str, Any]:
        if key not in self._buckets:
            self._buckets[key] = {
                "n": 0,
                "successes": 0,
                # Welford accumulators for duration
                "dur_mean": 0.0,
                "dur_m2": 0.0,
                # Welford accumulators for inconsistencies
                "inc_mean": 0.0,
                "inc_m2": 0.0,
            }
        return self._buckets[key]

    def process(self, result: Dict[str, Any]) -> None:
        """Ingest a single experiment result (O(1) memory)."""
        key = (result["failure_rate"], result["agent_type"])
        b = self._ensure_bucket(key)

        b["n"] += 1
        n = b["n"]

        if result["status"] == Status.SUCCESS:
            b["successes"] += 1

        # Welford online update — duration_ms
        dur = result["duration_ms"]
        delta = dur - b["dur_mean"]
        b["dur_mean"] += delta / n
        delta2 = dur - b["dur_mean"]
        b["dur_m2"] += delta * delta2

        # Welford online update — inconsistencies
        inc = result.get("inconsistencies_count", 0)
        delta_i = inc - b["inc_mean"]
        b["inc_mean"] += delta_i / n
        delta_i2 = inc - b["inc_mean"]
        b["inc_m2"] += delta_i * delta_i2

    def build_metrics(self) -> Dict[str, Any]:
        """Produce the aggregated_metrics.json-compatible dict."""
        import math

        # Group by failure_rate
        rates: Dict[float, Dict[str, Dict]] = defaultdict(dict)
        for (rate, agent_type), b in self._buckets.items():
            n = b["n"]
            std_dur = math.sqrt(b["dur_m2"] / n) if n > 1 else 0.0
            std_inc = math.sqrt(b["inc_m2"] / n) if n > 1 else 0.0
            success_rate = b["successes"] / n if n else 0.0
            std_sr = math.sqrt(success_rate * (1 - success_rate) / n) if n else 0.0

            rates[rate][agent_type] = {
                "n_runs": n,
                "success_rate": {"mean": success_rate, "std": round(std_sr, 6)},
                "duration_s": {
                    "mean": (b["dur_mean"] / 1000) if n else 0,
                    "std": round(std_dur / 1000, 6),
                },
                "inconsistencies": {
                    "mean": b["inc_mean"],
                    "std": round(std_inc, 6),
                },
            }

        n_agents = len(self._agent_names)
        metrics: Dict[str, Any] = {}
        for rate in sorted(rates):
            rate_key = str(rate)
            group = rates[rate]
            total = sum(v["n_runs"] for v in group.values())
            entry: Dict[str, Any] = {
                "failure_rate": rate,
                "n_experiments": total // n_agents,
            }
            for agent_name in self._agent_names:
                entry[agent_name] = group.get(agent_name, {})
            metrics[rate_key] = entry
        return metrics


class ParametricABTestRunner:
    def __init__(
        self,
        failure_rates: List[float],
        experiments_per_rate: int,
        output_dir: Path,
        seed: int = 42,
        logger: Optional[logging.Logger] = None,
        playbook_baseline_path: str = "assets/playbooks/baseline.json",
        playbook_training_path: str = "assets/playbooks/training.json",
        simulate_delays: bool = False,
        agents: Optional[List[AgentConfig]] = None,
    ):
        self.failure_rates = failure_rates
        self.experiments_per_rate = experiments_per_rate
        self.output_dir = output_dir
        self.base_seed = seed
        self.simulate_delays = simulate_delays
        self.logger = logger or logging.getLogger(__name__)

        # Build agent list: use explicit agents if provided, otherwise
        # fall back to the legacy two-agent baseline/playbook setup.
        if agents is not None:
            self.agents = agents
        else:
            self.agents = [
                AgentConfig(name="baseline", playbook_path=playbook_baseline_path),
                AgentConfig(name="playbook", playbook_path=playbook_training_path),
            ]

    @classmethod
    def from_ab_config(
        cls,
        failure_rates: List[float],
        experiments_per_rate: int,
        output_dir: Path,
        playbook_baseline_path: str = "assets/playbooks/baseline.json",
        playbook_training_path: str = "assets/playbooks/training.json",
        seed: int = 42,
        simulate_delays: bool = False,
        logger: Optional[logging.Logger] = None,
    ) -> "ParametricABTestRunner":
        """Factory method preserving the original two-agent A/B test interface."""
        return cls(
            failure_rates=failure_rates,
            experiments_per_rate=experiments_per_rate,
            output_dir=output_dir,
            seed=seed,
            logger=logger,
            playbook_baseline_path=playbook_baseline_path,
            playbook_training_path=playbook_training_path,
            simulate_delays=simulate_delays,
        )

    async def run_parametric_experiments(self) -> Dict[str, Any]:
        self.logger.info("Starting parametric experiments...")
        self.logger.info("Failure rates: %s", self.failure_rates)
        self.logger.info("Experiments per rate: %d", self.experiments_per_rate)
        n_agents = len(self.agents)
        self.logger.info(
            "Total: %d runs (%d agent types)",
            len(self.failure_rates) * self.experiments_per_rate * n_agents,
            n_agents,
        )

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Prepare CSV Streaming (GreenOps: Low Memory Footprint)
        csv_path = self.output_dir / "raw_results.csv"
        csv_keys = [
            "experiment_id", "agent_type", "outcome", "duration_ms",
            "steps_completed", "failed_at", "inconsistencies_count",
            "retries", "seed", "failure_rate"
        ]

        agent_names = [a.name for a in self.agents]
        aggregator = _StreamingAggregator(agent_names)
        count = 0

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_keys)
            writer.writeheader()

            async for result in self._experiment_generator():
                incons = self._calculate_inconsistency(result)
                result["inconsistencies_count"] = incons

                writer.writerow(self._flatten_result_for_csv(result))
                aggregator.process(result)
                count += 1
                logger.debug("Experiment result: inconsistencies=%s", incons)

        self.logger.info("Raw results streamed to %s", csv_path)

        # Save aggregated metrics from O(1) memory aggregator
        json_path = self.output_dir / "aggregated_metrics.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(aggregator.build_metrics(), f, indent=2)
        self.logger.info("Saved aggregated metrics to %s", json_path)

        return {"total_experiments": count}

    async def _run_single_experiment(
        self, agent_cfg: AgentConfig, failure_rate: float, seed: int
    ) -> Dict[str, Any]:
        """Run a single experiment with fresh infrastructure for any agent type."""
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
        agent = DeterministicAgent(
            tool_executor=circuit_breaker,
            playbook_path=agent_cfg.playbook_path,
            simulate_delays=self.simulate_delays,
        )
        result = await agent.run()
        result["agent_type"] = agent_cfg.name
        return result

    async def _experiment_generator(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generator that yields experiment results one by one.
        Iterates over all configured agents (N types) per failure rate.
        Reduces cognitive complexity of the main runner and enables streaming.
        """
        for i, rate in enumerate(self.failure_rates):
            self.logger.info("[%d/%d] Testing failure_rate=%.2f", i + 1, len(self.failure_rates), rate)

            for agent_cfg in self.agents:
                agent_name = agent_cfg.name
                prefix = agent_name.upper()[:4]

                self.logger.info("  Running %d %s experiments...", self.experiments_per_rate, agent_name)
                for j in range(self.experiments_per_rate):
                    seed = self.base_seed + (i * 1000) + j

                    result = await self._run_single_experiment(agent_cfg, rate, seed)

                    # Enrich identity
                    result["experiment_id"] = f"{prefix}-{rate}-{j}"
                    result["failure_rate"] = rate
                    result["seed"] = seed

                    if j % 5 == 0:
                        self.logger.debug("    %s run %d completed", agent_name, j)

                    yield result

            self.logger.info("   Completed batch for rate %s", rate)

    def _calculate_inconsistency(self, result: Dict) -> int:
        """
        Calcula si hubo inconsistencia de datos.
        Regla: Si falló en ERP o Shipping, es inconsistente (se cobró pero no se entregó).
        """
        if result["status"] == Status.SUCCESS:
            return 0

        failed_at = result.get("failed_at")

        if not failed_at and result["status"] == Status.FAILURE:
            self.logger.warning("Result marked failure but failed_at is empty: %s", result)

        if failed_at in (WorkflowStep.PLACE_ORDER, WorkflowStep.UPDATE_PET):
            return 1

        return 0

    def _flatten_result_for_csv(self, res: Dict) -> Dict:
        """Helper to flatten result dictionary for CSV writing."""
        return {
            "experiment_id": res["experiment_id"],
            "agent_type": res["agent_type"],
            "outcome": res["status"],
            "duration_ms": res["duration_ms"],
            "steps_completed": len(res["steps_completed"]),
            "failed_at": res.get("failed_at", ""),
            "inconsistencies_count": res.get("inconsistencies_count", 0),
            "retries": res.get("retries", 0),
            "seed": res["seed"],
            "failure_rate": res["failure_rate"]
        }
