"""PlaybookWriterAgent — Deterministic playbook synthesis from experiment data.

Analyzes raw_results.csv to detect failure patterns and generates candidate
playbook entries with appropriate recovery strategies. No LLM required.

Phase 9 (F.1): Autonomous Playbook Synthesis.
"""
from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chaos_engine.core.types import RetryStrategy, Status

logger = logging.getLogger(__name__)


@dataclass
class FailurePattern:
    """Aggregated failure statistics for a specific workflow step."""
    step: str
    total_attempts: int = 0
    failures: int = 0
    avg_duration_ms: float = 0.0
    _dur_sum: float = field(default=0.0, repr=False)

    @property
    def failure_rate(self) -> float:
        return self.failures / self.total_attempts if self.total_attempts else 0.0

    def record(self, outcome: str, duration_ms: float) -> None:
        self.total_attempts += 1
        self._dur_sum += duration_ms
        self.avg_duration_ms = self._dur_sum / self.total_attempts
        if outcome != Status.SUCCESS:
            self.failures += 1


def _select_strategy(pattern: FailurePattern) -> dict[str, Any]:
    """Select a recovery strategy based on failure pattern heuristics.

    Rules:
    - failure_rate < 10%: fail_fast (transient, not worth retrying)
    - failure_rate < 40%: retry with exponential backoff (intermittent)
    - failure_rate < 70%: retry with linear backoff + more retries (persistent)
    - failure_rate >= 70%: escalate to human (systemic issue)
    """
    rate = pattern.failure_rate

    if rate < 0.10:
        return {
            "strategy": RetryStrategy.FAIL_FAST,
            "reasoning": f"Low failure rate ({rate:.1%}). Transient errors, not worth retrying.",
            "config": {},
        }

    if rate < 0.40:
        return {
            "strategy": RetryStrategy.RETRY_EXPONENTIAL,
            "reasoning": f"Intermittent failures ({rate:.1%}). Exponential backoff recommended.",
            "config": {"base_delay": 1.0, "max_retries": 3},
        }

    if rate < 0.70:
        return {
            "strategy": RetryStrategy.RETRY_LINEAR,
            "reasoning": f"Persistent failures ({rate:.1%}). Linear backoff with extended retries.",
            "config": {"delay": 2.0, "max_retries": 5},
        }

    return {
        "strategy": RetryStrategy.ESCALATE_TO_HUMAN,
        "reasoning": f"Systemic failures ({rate:.1%}). Requires human investigation.",
        "config": {},
    }


class PlaybookWriterAgent:
    """Analyzes experiment results and synthesizes candidate playbook entries.

    Usage::

        writer = PlaybookWriterAgent()
        candidate = writer.analyze("reports/run_xyz/raw_results.csv")
        writer.save(candidate, "assets/playbooks/candidate.json")
    """

    def __init__(self, min_samples: int = 5) -> None:
        self.min_samples = min_samples

    def analyze(self, csv_path: str | Path) -> dict[str, Any]:
        """Read raw_results.csv and produce a candidate playbook dict.

        Returns a playbook-compatible dict with strategies per failed_at step.
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"Results file not found: {csv_path}")

        patterns = self._extract_patterns(csv_path)
        playbook = self._synthesize(patterns)

        logger.info(
            "Analyzed %s: %d failure patterns -> %d playbook entries",
            csv_path.name,
            len(patterns),
            len(playbook) - 1,  # exclude 'default'
        )
        return playbook

    def _extract_patterns(self, csv_path: Path) -> dict[str, FailurePattern]:
        """Parse CSV and aggregate failure patterns by step."""
        patterns: dict[str, FailurePattern] = defaultdict(lambda: FailurePattern(step=""))

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                outcome = row.get("outcome", "")
                failed_at = row.get("failed_at", "")
                duration_ms = float(row.get("duration_ms", 0))

                # Track all steps that appear as failure points
                if failed_at and outcome != Status.SUCCESS:
                    if failed_at not in patterns:
                        patterns[failed_at] = FailurePattern(step=failed_at)
                    patterns[failed_at].record(outcome, duration_ms)

                # Also track successful runs per step for baseline rates
                if outcome == Status.SUCCESS:
                    for step_name in patterns:
                        patterns[step_name].total_attempts += 1

        return dict(patterns)

    def _synthesize(self, patterns: dict[str, FailurePattern]) -> dict[str, Any]:
        """Convert failure patterns into playbook strategy entries."""
        playbook: dict[str, Any] = {}

        for step, pattern in patterns.items():
            if pattern.total_attempts < self.min_samples:
                logger.debug(
                    "Skipping %s: only %d samples (min=%d)",
                    step, pattern.total_attempts, self.min_samples,
                )
                continue

            strategy = _select_strategy(pattern)
            # Map step name to playbook error codes (500 as default error)
            playbook[step] = {"500": strategy}

        # Always include a default fallback
        playbook["default"] = {
            "strategy": RetryStrategy.ESCALATE_TO_HUMAN,
            "reasoning": "Unknown error scenario. Escalate for investigation.",
            "config": {},
        }

        return playbook

    def save(self, playbook: dict[str, Any], output_path: str | Path) -> Path:
        """Write candidate playbook to JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(playbook, f, indent=2)

        logger.info("Saved candidate playbook to %s", output_path)
        return output_path

    def compare_with_existing(
        self,
        candidate: dict[str, Any],
        existing_path: str | Path,
    ) -> dict[str, Any]:
        """Compare candidate playbook against existing one.

        Returns a diff summary showing new, changed, and unchanged entries.
        """
        existing_path = Path(existing_path)
        if not existing_path.exists():
            return {"new": list(candidate.keys()), "changed": [], "unchanged": []}

        with open(existing_path, "r", encoding="utf-8") as f:
            existing = json.load(f)

        new_keys = [k for k in candidate if k not in existing and k != "default"]
        changed = []
        unchanged = []

        for key in candidate:
            if key == "default":
                continue
            if key in existing and candidate[key] != existing[key]:
                changed.append(key)
            elif key in existing and candidate[key] == existing[key]:
                unchanged.append(key)

        return {"new": new_keys, "changed": changed, "unchanged": unchanged}
