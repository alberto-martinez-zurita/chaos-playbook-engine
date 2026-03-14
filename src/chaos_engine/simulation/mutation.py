"""Playbook Mutation & Evolution — deterministic playbook optimization (G.2).

Generates playbook variants by mutating strategy parameters, runs parametric
experiments on each variant, and selects the best performer. No LLM needed.

Usage::

    evolver = PlaybookEvolver(
        base_playbook_path="assets/playbooks/training.json",
        failure_rates=[0.1, 0.3, 0.5],
        experiments_per_rate=20,
    )
    best = await evolver.evolve(generations=3, variants_per_gen=4)
"""
from __future__ import annotations

import copy
import json
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chaos_engine.core.types import RetryStrategy

logger = logging.getLogger(__name__)

# Mutable strategy parameters and their valid ranges
_PARAM_RANGES: dict[str, tuple[float, float]] = {
    "base_delay": (0.5, 10.0),
    "delay": (0.5, 10.0),
    "wait_seconds": (1.0, 15.0),
    "max_retries": (1, 8),
}

# Strategies that can be substituted for each other
_RETRY_STRATEGIES = [
    RetryStrategy.RETRY_LINEAR,
    RetryStrategy.RETRY_EXPONENTIAL,
    RetryStrategy.WAIT_AND_RETRY,
]


@dataclass
class MutationResult:
    """Result of evaluating a playbook variant."""
    variant_id: str
    playbook: dict[str, Any]
    success_rate: float
    avg_duration_s: float
    avg_inconsistencies: float
    score: float = 0.0


@dataclass
class PlaybookEvolver:
    """Evolves playbook strategies through mutation and selection.

    Each generation:
    1. Mutate the current best playbook N times
    2. Run parametric experiments on each variant
    3. Score variants by: success_rate * 100 - inconsistencies * 50 - duration * 2
    4. Select the best as parent for next generation
    """
    base_playbook_path: str
    failure_rates: list[float] = field(default_factory=lambda: [0.1, 0.3, 0.5])
    experiments_per_rate: int = 20
    seed: int = 42
    output_dir: str = "reports/evolution"
    mutation_rate: float = 0.3

    def _load_base(self) -> dict[str, Any]:
        with open(self.base_playbook_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def mutate(self, playbook: dict[str, Any], rng: random.Random) -> dict[str, Any]:
        """Create a mutated copy of the playbook.

        Mutations:
        - Swap retry strategy type (linear ↔ exponential ↔ wait_and_retry)
        - Adjust numeric parameters (delay, max_retries) by ±30%
        """
        mutant = copy.deepcopy(playbook)

        for api_key, api_rules in mutant.items():
            if api_key == "default" or not isinstance(api_rules, dict):
                continue

            for code, entry in api_rules.items():
                if not isinstance(entry, dict) or rng.random() > self.mutation_rate:
                    continue

                strategy = entry.get("strategy", "")
                config = entry.get("config", {})

                # Mutation 1: swap strategy
                if strategy in _RETRY_STRATEGIES and rng.random() < 0.2:
                    new_strategy = rng.choice(_RETRY_STRATEGIES)
                    entry["strategy"] = new_strategy
                    # Ensure config keys match new strategy
                    if new_strategy == RetryStrategy.RETRY_EXPONENTIAL and "base_delay" not in config:
                        config["base_delay"] = config.pop("delay", 1.0)
                    elif new_strategy == RetryStrategy.RETRY_LINEAR and "delay" not in config:
                        config["delay"] = config.pop("base_delay", 1.0)
                    elif new_strategy == RetryStrategy.WAIT_AND_RETRY and "wait_seconds" not in config:
                        config["wait_seconds"] = config.pop("delay", config.pop("base_delay", 5.0))

                # Mutation 2: tweak numeric parameters
                for param, (lo, hi) in _PARAM_RANGES.items():
                    if param in config:
                        current = config[param]
                        delta = current * rng.uniform(-0.3, 0.3)
                        new_val = max(lo, min(hi, current + delta))
                        if param == "max_retries":
                            new_val = int(round(new_val))
                        else:
                            new_val = round(new_val, 2)
                        config[param] = new_val

        return mutant

    async def evaluate_variant(
        self, playbook: dict[str, Any], variant_id: str, work_dir: Path
    ) -> MutationResult:
        """Run parametric experiments with a playbook variant and score it."""
        from chaos_engine.simulation.parametric import AgentConfig, ParametricABTestRunner

        # Write variant to temp file
        variant_path = work_dir / f"{variant_id}.json"
        with open(variant_path, "w", encoding="utf-8") as f:
            json.dump(playbook, f, indent=2)

        output_dir = work_dir / variant_id
        runner = ParametricABTestRunner(
            failure_rates=self.failure_rates,
            experiments_per_rate=self.experiments_per_rate,
            output_dir=output_dir,
            seed=self.seed,
            simulate_delays=False,
            agents=[AgentConfig(name="variant", playbook_path=str(variant_path))],
        )

        await runner.run_parametric_experiments()

        # Read metrics
        metrics_path = output_dir / "aggregated_metrics.json"
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        # Aggregate across rates
        total_success = 0.0
        total_duration = 0.0
        total_incons = 0.0
        n_rates = 0

        for rate_key, rate_data in metrics.items():
            variant_data = rate_data.get("variant", {})
            if not variant_data:
                continue
            total_success += variant_data.get("success_rate", {}).get("mean", 0.0)
            total_duration += variant_data.get("duration_s", {}).get("mean", 0.0)
            total_incons += variant_data.get("inconsistencies", {}).get("mean", 0.0)
            n_rates += 1

        avg_success = total_success / n_rates if n_rates else 0.0
        avg_duration = total_duration / n_rates if n_rates else 0.0
        avg_incons = total_incons / n_rates if n_rates else 0.0

        # Score: prioritize success, penalize inconsistencies, mild duration penalty
        score = avg_success * 100 - avg_incons * 50 - avg_duration * 2

        return MutationResult(
            variant_id=variant_id,
            playbook=playbook,
            success_rate=avg_success,
            avg_duration_s=avg_duration,
            avg_inconsistencies=avg_incons,
            score=score,
        )

    async def evolve(
        self, generations: int = 3, variants_per_gen: int = 4
    ) -> MutationResult:
        """Run the evolutionary loop and return the best variant."""
        work_dir = Path(self.output_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        rng = random.Random(self.seed)
        current_best_playbook = self._load_base()

        # Evaluate baseline first
        logger.info("Evaluating baseline playbook...")
        best = await self.evaluate_variant(current_best_playbook, "gen0_baseline", work_dir)
        logger.info("Baseline score: %.2f (success=%.2f%%)", best.score, best.success_rate * 100)

        for gen in range(1, generations + 1):
            logger.info("Generation %d/%d: creating %d variants...", gen, generations, variants_per_gen)

            results: list[MutationResult] = []
            for v in range(variants_per_gen):
                variant_id = f"gen{gen}_v{v}"
                mutant = self.mutate(current_best_playbook, rng)
                result = await self.evaluate_variant(mutant, variant_id, work_dir)
                results.append(result)
                logger.info(
                    "  %s: score=%.2f success=%.1f%% incons=%.3f",
                    variant_id, result.score, result.success_rate * 100, result.avg_inconsistencies,
                )

            # Select best from this generation (include previous best)
            results.append(best)
            gen_best = max(results, key=lambda r: r.score)

            if gen_best.score > best.score:
                logger.info(
                    "New best: %s (score %.2f > %.2f)", gen_best.variant_id, gen_best.score, best.score
                )
                best = gen_best
                current_best_playbook = gen_best.playbook
            else:
                logger.info("No improvement in generation %d (best remains %.2f)", gen, best.score)

        # Save best playbook
        best_path = work_dir / "best_playbook.json"
        with open(best_path, "w", encoding="utf-8") as f:
            json.dump(best.playbook, f, indent=2)
        logger.info("Evolution complete. Best saved to %s (score=%.2f)", best_path, best.score)

        return best
