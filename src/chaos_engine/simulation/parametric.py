"""
ParametricABTestRunner - Orchestrator for multi-rate experiments.
Updated with DEBUGGING for Inconsistency Calculation.
REFACTORED: Streaming/Generator pattern for GreenOps compliance.
"""
from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from chaos_engine.simulation.runner import ABTestRunner

logger = logging.getLogger(__name__)


class _StreamingAggregator:
    """Online aggregator using Welford's algorithm for mean and variance.

    Processes one result at a time — O(1) memory per rate/agent_type bucket.
    Replaces the old ``all_results_buffer`` list that required O(N) memory.
    """

    def __init__(self) -> None:
        # key: (failure_rate, agent_type) -> stats accumulator
        self._buckets: Dict[tuple[float, str], Dict[str, Any]] = {}

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

        if result["status"] == "success":
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

        metrics: Dict[str, Any] = {}
        for rate in sorted(rates):
            rate_key = str(rate)
            group = rates[rate]
            total = sum(v["n_runs"] for v in group.values())
            metrics[rate_key] = {
                "failure_rate": rate,
                "n_experiments": total // 2,
                "baseline": group.get("baseline", {}),
                "playbook": group.get("playbook", {}),
            }
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
    ):
        self.failure_rates = failure_rates
        self.experiments_per_rate = experiments_per_rate
        self.output_dir = output_dir
        self.base_seed = seed
        self.ab_runner = ABTestRunner(
            playbook_baseline_path=playbook_baseline_path,
            playbook_training_path=playbook_training_path,
            simulate_delays=simulate_delays,
            logger=logger,
        )
        self.logger = logger or logging.getLogger(__name__)

    async def run_parametric_experiments(self) -> Dict[str, Any]:
        self.logger.info("Starting parametric experiments...")
        self.logger.info("Failure rates: %s", self.failure_rates)
        self.logger.info("Experiments per rate: %d", self.experiments_per_rate)
        self.logger.info("Total: %d runs", len(self.failure_rates) * self.experiments_per_rate * 2)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare CSV Streaming (GreenOps: Low Memory Footprint)
        csv_path = self.output_dir / "raw_results.csv"
        csv_keys = [
            "experiment_id", "agent_type", "outcome", "duration_ms", 
            "steps_completed", "failed_at", "inconsistencies_count",
            "retries", "seed", "failure_rate"
        ]

        aggregator = _StreamingAggregator()
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

    async def _experiment_generator(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generator that yields experiment results one by one.
        Reduces cognitive complexity of the main runner and enables streaming.
        """
        for i, rate in enumerate(self.failure_rates):
            self.logger.info("[%d/%d] Testing failure_rate=%.2f", i + 1, len(self.failure_rates), rate)
            
            # 1. Baseline Experiments
            self.logger.info("  Running %d Baseline experiments...", self.experiments_per_rate)
            for j in range(self.experiments_per_rate):
                seed = self.base_seed + (i * 1000) + j
                
                result = await self.ab_runner.run_experiment(
                    agent_type="baseline",
                    failure_rate=rate,
                    seed=seed
                )
                
                # Enrich identity
                result["experiment_id"] = f"BASE-{rate}-{j}"
                result["failure_rate"] = rate
                result["seed"] = seed
                
                if j % 5 == 0:
                    self.logger.debug("    Baseline run %d completed", j)
                
                yield result

            # 2. Playbook Experiments
            self.logger.info("  Running %d Playbook experiments...", self.experiments_per_rate)
            for j in range(self.experiments_per_rate):
                seed = self.base_seed + (i * 1000) + j 
                
                result = await self.ab_runner.run_experiment(
                    agent_type="playbook",
                    failure_rate=rate,
                    seed=seed
                )
                
                # Enrich identity
                result["experiment_id"] = f"PLAY-{rate}-{j}"
                result["failure_rate"] = rate
                result["seed"] = seed
                
                if j % 5 == 0:
                    self.logger.debug("    Playbook run %d completed", j)
                
                yield result
            
            self.logger.info("   Completed batch for rate %s", rate)

    def _calculate_inconsistency(self, result: Dict) -> int:
        """
        Calcula si hubo inconsistencia de datos.
        Regla: Si falló en ERP o Shipping, es inconsistente (se cobró pero no se entregó).
        """
        if result["status"] == "success":
            return 0
            
        failed_at = result.get("failed_at")
        
        # Debug visual si falla la detección
        if not failed_at and result["status"] == "failure":
            self.logger.warning("Result marked failure but failed_at is empty: %s", result)

        # Lógica de negocio:
        # get_inventory/find_pets_by_status fail -> Safe (0)
        # place_order/update_pet_status fail -> Unsafe (1)
        if failed_at in ["place_order", "update_pet_status"]:
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

