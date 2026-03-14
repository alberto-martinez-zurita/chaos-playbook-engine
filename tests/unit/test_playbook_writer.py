"""Tests for PlaybookWriterAgent — deterministic playbook synthesis."""
from __future__ import annotations

import csv
import json

import pytest

from chaos_engine.agents.playbook_writer import (
    FailurePattern,
    PlaybookWriterAgent,
    _select_strategy,
)
from chaos_engine.core.types import RetryStrategy


# ---------------------------------------------------------------------------
# FailurePattern
# ---------------------------------------------------------------------------

def test_failure_pattern_rate():
    p = FailurePattern(step="get_inventory")
    p.record("failure", 100.0)
    p.record("success", 50.0)
    p.record("failure", 120.0)
    assert p.failure_rate == pytest.approx(2 / 3)
    assert p.total_attempts == 3


def test_failure_pattern_zero_attempts():
    p = FailurePattern(step="x")
    assert p.failure_rate == 0.0


# ---------------------------------------------------------------------------
# Strategy selection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rate,expected_strategy", [
    (0.05, RetryStrategy.FAIL_FAST),
    (0.25, RetryStrategy.RETRY_EXPONENTIAL),
    (0.55, RetryStrategy.RETRY_LINEAR),
    (0.85, RetryStrategy.ESCALATE_TO_HUMAN),
])
def test_strategy_selection(rate, expected_strategy):
    p = FailurePattern(step="test", total_attempts=100, failures=int(rate * 100))
    result = _select_strategy(p)
    assert result["strategy"] == expected_strategy


# ---------------------------------------------------------------------------
# PlaybookWriterAgent.analyze
# ---------------------------------------------------------------------------

def _write_csv(path, rows):
    fieldnames = ["experiment_id", "agent_type", "outcome", "duration_ms",
                  "steps_completed", "failed_at", "inconsistencies_count",
                  "retries", "seed", "failure_rate"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            full = {k: "" for k in fieldnames}
            full.update(row)
            writer.writerow(full)


def test_analyze_generates_playbook(tmp_path):
    csv_path = tmp_path / "raw_results.csv"
    rows = []
    # 20 failures at place_order, 5 successes
    for i in range(20):
        rows.append({
            "experiment_id": f"TEST-{i}",
            "outcome": "failure",
            "duration_ms": "150",
            "failed_at": "place_order",
            "failure_rate": "0.3",
        })
    for i in range(5):
        rows.append({
            "experiment_id": f"OK-{i}",
            "outcome": "success",
            "duration_ms": "80",
            "failed_at": "",
            "failure_rate": "0.0",
        })
    _write_csv(csv_path, rows)

    writer = PlaybookWriterAgent(min_samples=5)
    playbook = writer.analyze(csv_path)

    assert "place_order" in playbook
    assert "default" in playbook
    assert "500" in playbook["place_order"]


def test_analyze_skips_low_sample_patterns(tmp_path):
    csv_path = tmp_path / "raw_results.csv"
    rows = [
        {"experiment_id": "T-1", "outcome": "failure", "duration_ms": "100",
         "failed_at": "get_inventory", "failure_rate": "0.5"},
    ]
    _write_csv(csv_path, rows)

    writer = PlaybookWriterAgent(min_samples=10)
    playbook = writer.analyze(csv_path)

    # Only default should be present (get_inventory has < 10 samples)
    assert "get_inventory" not in playbook
    assert "default" in playbook


def test_save_and_compare(tmp_path):
    writer = PlaybookWriterAgent()

    existing = {"place_order": {"500": {"strategy": "fail_fast"}}, "default": {}}
    existing_path = tmp_path / "existing.json"
    with open(existing_path, "w") as f:
        json.dump(existing, f)

    candidate = {
        "place_order": {"500": {"strategy": "retry_exponential_backoff"}},
        "update_pet_status": {"500": {"strategy": "retry_linear_backoff"}},
        "default": {},
    }

    diff = writer.compare_with_existing(candidate, existing_path)
    assert "update_pet_status" in diff["new"]
    assert "place_order" in diff["changed"]


def test_analyze_file_not_found():
    writer = PlaybookWriterAgent()
    with pytest.raises(FileNotFoundError):
        writer.analyze("nonexistent.csv")


def test_save_creates_directories(tmp_path):
    writer = PlaybookWriterAgent()
    deep_path = tmp_path / "a" / "b" / "c" / "playbook.json"
    writer.save({"default": {}}, deep_path)
    assert deep_path.exists()
