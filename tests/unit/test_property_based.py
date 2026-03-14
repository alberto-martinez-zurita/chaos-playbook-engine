"""Property-based tests using Hypothesis (B.5).

Tests invariants that must hold for all inputs, not just specific examples.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from chaos_engine.agents.deterministic import DeterministicAgent
from chaos_engine.chaos.config import ChaosConfig
from chaos_engine.core.types import RetryStrategy


# ---------------------------------------------------------------------------
# ChaosConfig.should_inject_failure — rate bounds
# ---------------------------------------------------------------------------

@given(rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
def test_chaos_config_rate_zero_never_fails(rate: float):
    """failure_rate=0 should never inject failure."""
    config = ChaosConfig(failure_rate=0.0, seed=42)
    # With rate 0.0, should_inject_failure should always be False
    assert config.should_inject_failure() is False


@given(seed=st.integers(min_value=0, max_value=10000))
def test_chaos_config_rate_one_always_fails(seed: int):
    """failure_rate=1.0 with enabled=True should always inject failure."""
    config = ChaosConfig(enabled=True, failure_rate=1.0, seed=seed)
    assert config.should_inject_failure() is True


@given(
    rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    seed=st.integers(min_value=0, max_value=100000),
)
def test_chaos_config_returns_bool(rate: float, seed: int):
    """should_inject_failure always returns a bool."""
    config = ChaosConfig(enabled=True, failure_rate=rate, seed=seed)
    result = config.should_inject_failure()
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# DeterministicAgent._calculate_delay — invariants per strategy
# ---------------------------------------------------------------------------

@given(attempt=st.integers(min_value=1, max_value=20))
def test_linear_delay_increases_with_attempt(attempt: int):
    """Linear backoff delay should scale linearly with attempt number."""
    delay = 2.0
    config = {"delay": delay}
    result = DeterministicAgent._calculate_delay(
        RetryStrategy.RETRY_LINEAR, config, attempt
    )
    assert result == pytest.approx(delay * attempt)


@given(attempt=st.integers(min_value=1, max_value=10))
def test_exponential_delay_doubles_each_attempt(attempt: int):
    """Exponential backoff should double with each attempt."""
    base = 1.0
    config = {"base_delay": base}
    result = DeterministicAgent._calculate_delay(
        RetryStrategy.RETRY_EXPONENTIAL, config, attempt
    )
    assert result == pytest.approx(base * (2 ** (attempt - 1)))


@given(attempt=st.integers(min_value=1, max_value=20))
def test_wait_and_retry_constant(attempt: int):
    """Wait-and-retry should return constant delay regardless of attempt."""
    wait = 5.0
    config = {"wait_seconds": wait}
    result = DeterministicAgent._calculate_delay(
        RetryStrategy.WAIT_AND_RETRY, config, attempt
    )
    assert result == pytest.approx(wait)


@given(
    delay=st.floats(min_value=0.1, max_value=100.0, allow_nan=False),
    attempt=st.integers(min_value=1, max_value=10),
)
def test_delay_is_always_positive(delay: float, attempt: int):
    """Calculated delay must always be positive for any valid input."""
    config = {"delay": delay, "base_delay": delay, "wait_seconds": delay}
    for strategy in (
        RetryStrategy.RETRY_LINEAR,
        RetryStrategy.RETRY_EXPONENTIAL,
        RetryStrategy.WAIT_AND_RETRY,
    ):
        result = DeterministicAgent._calculate_delay(strategy, config, attempt)
        assert result > 0, f"Negative delay for {strategy} attempt={attempt}"


# ---------------------------------------------------------------------------
# _StreamingAggregator — Welford invariants
# ---------------------------------------------------------------------------

@given(
    values=st.lists(
        st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=50,
    )
)
def test_welford_mean_matches_naive(values: list[float]):
    """Welford online mean should match naive calculation."""
    from chaos_engine.simulation.parametric import _StreamingAggregator
    from chaos_engine.core.types import Status

    agg = _StreamingAggregator(["test"])
    for i, v in enumerate(values):
        agg.process({
            "failure_rate": 0.1,
            "agent_type": "test",
            "status": Status.SUCCESS,
            "duration_ms": v,
            "inconsistencies_count": 0,
        })

    metrics = agg.build_metrics()
    computed_mean = metrics["0.1"]["test"]["duration_s"]["mean"]
    expected_mean = sum(values) / len(values) / 1000

    assert computed_mean == pytest.approx(expected_mean, rel=1e-6)
