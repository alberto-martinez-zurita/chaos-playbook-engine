"""Tests for PlaybookEvolver — mutation and evolution (G.2)."""
from __future__ import annotations

import json
import random

import pytest

from chaos_engine.core.types import RetryStrategy
from chaos_engine.simulation.mutation import PlaybookEvolver, MutationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_playbook() -> dict:
    return {
        "get_inventory": {
            "500": {
                "strategy": "retry_exponential_backoff",
                "config": {"base_delay": 1.0, "max_retries": 3},
            },
        },
        "place_order": {
            "408": {
                "strategy": "retry_linear_backoff",
                "config": {"delay": 2.0, "max_retries": 3},
            },
        },
        "default": {
            "strategy": "escalate_to_human",
            "config": {},
        },
    }


# ---------------------------------------------------------------------------
# Mutation
# ---------------------------------------------------------------------------

def test_mutate_preserves_structure():
    """Mutant should have same top-level keys as original."""
    evolver = PlaybookEvolver(base_playbook_path="", mutation_rate=1.0)
    rng = random.Random(42)
    original = _sample_playbook()
    mutant = evolver.mutate(original, rng)

    assert set(mutant.keys()) == set(original.keys())
    assert "default" in mutant
    # Default should not be mutated
    assert mutant["default"]["strategy"] == "escalate_to_human"


def test_mutate_does_not_modify_original():
    """Mutation must not modify the input playbook (deep copy)."""
    evolver = PlaybookEvolver(base_playbook_path="", mutation_rate=1.0)
    rng = random.Random(42)
    original = _sample_playbook()
    original_copy = json.loads(json.dumps(original))

    evolver.mutate(original, rng)

    assert original == original_copy


def test_mutate_changes_something_with_high_rate():
    """With mutation_rate=1.0 and many calls, at least one value should change."""
    evolver = PlaybookEvolver(base_playbook_path="", mutation_rate=1.0)
    original = _sample_playbook()

    # Try multiple seeds — at least one should produce a different playbook
    any_changed = False
    for seed in range(20):
        rng = random.Random(seed)
        mutant = evolver.mutate(original, rng)
        if mutant != original:
            any_changed = True
            break

    assert any_changed, "No mutation occurred across 20 seeds with rate=1.0"


def test_mutate_respects_param_bounds():
    """Mutated parameters should stay within defined bounds."""
    evolver = PlaybookEvolver(base_playbook_path="", mutation_rate=1.0)

    for seed in range(50):
        rng = random.Random(seed)
        mutant = evolver.mutate(_sample_playbook(), rng)

        for api_key, api_rules in mutant.items():
            if api_key == "default" or not isinstance(api_rules, dict):
                continue
            for code, entry in api_rules.items():
                config = entry.get("config", {})
                if "base_delay" in config:
                    assert 0.5 <= config["base_delay"] <= 10.0
                if "delay" in config:
                    assert 0.5 <= config["delay"] <= 10.0
                if "max_retries" in config:
                    assert 1 <= config["max_retries"] <= 8
                if "wait_seconds" in config:
                    assert 1.0 <= config["wait_seconds"] <= 15.0


def test_mutate_with_zero_rate_changes_nothing():
    """With mutation_rate=0, playbook should be identical (no mutations)."""
    evolver = PlaybookEvolver(base_playbook_path="", mutation_rate=0.0)
    rng = random.Random(42)
    original = _sample_playbook()
    mutant = evolver.mutate(original, rng)

    assert mutant == original


# ---------------------------------------------------------------------------
# MutationResult scoring
# ---------------------------------------------------------------------------

def test_mutation_result_score_ordering():
    """Higher success rate should produce higher score."""
    good = MutationResult(
        variant_id="good", playbook={},
        success_rate=0.9, avg_duration_s=0.5, avg_inconsistencies=0.0,
    )
    bad = MutationResult(
        variant_id="bad", playbook={},
        success_rate=0.3, avg_duration_s=0.5, avg_inconsistencies=0.5,
    )
    good.score = good.success_rate * 100 - good.avg_inconsistencies * 50 - good.avg_duration_s * 2
    bad.score = bad.success_rate * 100 - bad.avg_inconsistencies * 50 - bad.avg_duration_s * 2

    assert good.score > bad.score


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def test_parser_evolve_subcommand():
    from chaos_engine.__main__ import build_parser

    parser = build_parser()
    args = parser.parse_args([
        "evolve", "--playbook", "training.json",
        "--generations", "5", "--variants", "8",
        "--mutation-rate", "0.5",
    ])
    assert args.command == "evolve"
    assert args.playbook == "training.json"
    assert args.generations == 5
    assert args.variants == 8
    assert args.mutation_rate == 0.5


# ---------------------------------------------------------------------------
# Evolution E2E (small scale)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evolve_produces_best_playbook(tmp_path):
    """Full evolution loop with 1 generation and 2 variants."""
    base_playbook = _sample_playbook()
    base_path = tmp_path / "base.json"
    with open(base_path, "w") as f:
        json.dump(base_playbook, f)

    evolver = PlaybookEvolver(
        base_playbook_path=str(base_path),
        failure_rates=[0.0, 0.3],
        experiments_per_rate=3,
        seed=42,
        output_dir=str(tmp_path / "evolution"),
        mutation_rate=0.5,
    )

    best = await evolver.evolve(generations=1, variants_per_gen=2)

    assert isinstance(best, MutationResult)
    assert best.score != 0
    assert (tmp_path / "evolution" / "best_playbook.json").exists()
