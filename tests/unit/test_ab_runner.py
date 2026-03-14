from __future__ import annotations

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chaos_engine.simulation.runner import ABTestRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUCCESS_RESULT: Dict[str, Any] = {
    "status": "success",
    "steps_completed": [
        "get_inventory",
        "find_pets_by_status",
        "place_order",
        "update_pet_status",
    ],
    "failed_at": None,
    "duration_ms": 42.0,
    "retries": 0,
    "simulated_delay_s": 0.0,
    "outcome": "success",
    "agent_type": "",  # filled by runner
}

_FAILURE_RESULT: Dict[str, Any] = {
    "status": "failure",
    "steps_completed": ["get_inventory"],
    "failed_at": "find_pets_by_status",
    "duration_ms": 10.0,
    "retries": 0,
    "simulated_delay_s": 0.0,
    "outcome": "failure",
    "agent_type": "",
}


def _make_runner(baseline: str = "assets/playbooks/baseline.json",
                 training: str = "assets/playbooks/training.json",
                 simulate_delays: bool = False) -> ABTestRunner:
    return ABTestRunner(
        playbook_baseline_path=baseline,
        playbook_training_path=training,
        simulate_delays=simulate_delays,
    )


# ---------------------------------------------------------------------------
# 1. Result contains all required keys
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_result_contains_required_keys():
    """run_experiment must return all keys that downstream consumers expect."""
    runner = _make_runner()

    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=dict(_SUCCESS_RESULT))

    with (
        patch("chaos_engine.simulation.runner.ChaosProxy") as MockChaosProxy,
        patch("chaos_engine.simulation.runner.CircuitBreakerProxy") as MockCBProxy,
        patch("chaos_engine.simulation.runner.DeterministicAgent", return_value=mock_agent_instance),
    ):
        MockChaosProxy.return_value = MagicMock()
        MockCBProxy.return_value = MagicMock()

        result = await runner.run_experiment(agent_type="baseline", failure_rate=0.0, seed=42)

    required_keys = {"status", "steps_completed", "failed_at", "duration_ms", "agent_type"}
    assert required_keys.issubset(result.keys())


# ---------------------------------------------------------------------------
# 2. agent_type is stamped onto the result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_type_is_stamped_baseline():
    """agent_type='baseline' must appear in the returned dict."""
    runner = _make_runner()

    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=dict(_SUCCESS_RESULT))

    with (
        patch("chaos_engine.simulation.runner.ChaosProxy"),
        patch("chaos_engine.simulation.runner.CircuitBreakerProxy"),
        patch("chaos_engine.simulation.runner.DeterministicAgent", return_value=mock_agent_instance),
    ):
        result = await runner.run_experiment(agent_type="baseline", failure_rate=0.0, seed=1)

    assert result["agent_type"] == "baseline"


@pytest.mark.asyncio
async def test_agent_type_is_stamped_playbook():
    """agent_type='playbook' must appear in the returned dict."""
    runner = _make_runner()

    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=dict(_SUCCESS_RESULT))

    with (
        patch("chaos_engine.simulation.runner.ChaosProxy"),
        patch("chaos_engine.simulation.runner.CircuitBreakerProxy"),
        patch("chaos_engine.simulation.runner.DeterministicAgent", return_value=mock_agent_instance),
    ):
        result = await runner.run_experiment(agent_type="playbook", failure_rate=0.0, seed=1)

    assert result["agent_type"] == "playbook"


# ---------------------------------------------------------------------------
# 3. Playbook path selection: baseline vs playbook agent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_baseline_agent_uses_baseline_playbook():
    """When agent_type='baseline', DeterministicAgent must receive the baseline playbook path."""
    baseline_path = "my/baseline.json"
    training_path = "my/training.json"
    runner = _make_runner(baseline=baseline_path, training=training_path)

    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=dict(_SUCCESS_RESULT))

    with (
        patch("chaos_engine.simulation.runner.ChaosProxy"),
        patch("chaos_engine.simulation.runner.CircuitBreakerProxy"),
        patch("chaos_engine.simulation.runner.DeterministicAgent", return_value=mock_agent_instance) as MockAgent,
    ):
        await runner.run_experiment(agent_type="baseline", failure_rate=0.0, seed=0)

    # Inspect the keyword arguments passed to DeterministicAgent
    _, kwargs = MockAgent.call_args
    assert kwargs["playbook_path"] == baseline_path


@pytest.mark.asyncio
async def test_playbook_agent_uses_training_playbook():
    """When agent_type='playbook', DeterministicAgent must receive the training playbook path."""
    baseline_path = "my/baseline.json"
    training_path = "my/training.json"
    runner = _make_runner(baseline=baseline_path, training=training_path)

    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=dict(_SUCCESS_RESULT))

    with (
        patch("chaos_engine.simulation.runner.ChaosProxy"),
        patch("chaos_engine.simulation.runner.CircuitBreakerProxy"),
        patch("chaos_engine.simulation.runner.DeterministicAgent", return_value=mock_agent_instance) as MockAgent,
    ):
        await runner.run_experiment(agent_type="playbook", failure_rate=0.0, seed=0)

    _, kwargs = MockAgent.call_args
    assert kwargs["playbook_path"] == training_path


# ---------------------------------------------------------------------------
# 4. Fresh infrastructure per experiment (no state leakage)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fresh_chaos_proxy_created_per_experiment():
    """ChaosProxy must be instantiated once per run_experiment call."""
    runner = _make_runner()

    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=dict(_SUCCESS_RESULT))

    with (
        patch("chaos_engine.simulation.runner.ChaosProxy") as MockChaosProxy,
        patch("chaos_engine.simulation.runner.CircuitBreakerProxy"),
        patch("chaos_engine.simulation.runner.DeterministicAgent", return_value=mock_agent_instance),
    ):
        await runner.run_experiment(agent_type="baseline", failure_rate=0.1, seed=7)
        await runner.run_experiment(agent_type="baseline", failure_rate=0.1, seed=7)

    # Two experiments → two fresh ChaosProxy instances
    assert MockChaosProxy.call_count == 2


@pytest.mark.asyncio
async def test_fresh_circuit_breaker_created_per_experiment():
    """CircuitBreakerProxy must be instantiated once per run_experiment call."""
    runner = _make_runner()

    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=dict(_SUCCESS_RESULT))

    with (
        patch("chaos_engine.simulation.runner.ChaosProxy"),
        patch("chaos_engine.simulation.runner.CircuitBreakerProxy") as MockCB,
        patch("chaos_engine.simulation.runner.DeterministicAgent", return_value=mock_agent_instance),
    ):
        await runner.run_experiment(agent_type="baseline", failure_rate=0.1, seed=7)
        await runner.run_experiment(agent_type="baseline", failure_rate=0.1, seed=7)

    assert MockCB.call_count == 2


# ---------------------------------------------------------------------------
# 5. ChaosProxy receives correct failure_rate and seed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chaos_proxy_receives_correct_parameters():
    """ChaosProxy must be called with the failure_rate and seed from run_experiment."""
    runner = _make_runner()

    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=dict(_SUCCESS_RESULT))

    with (
        patch("chaos_engine.simulation.runner.ChaosProxy") as MockChaosProxy,
        patch("chaos_engine.simulation.runner.CircuitBreakerProxy"),
        patch("chaos_engine.simulation.runner.DeterministicAgent", return_value=mock_agent_instance),
    ):
        await runner.run_experiment(agent_type="baseline", failure_rate=0.35, seed=99)

    _, kwargs = MockChaosProxy.call_args
    assert kwargs["failure_rate"] == 0.35
    assert kwargs["seed"] == 99


# ---------------------------------------------------------------------------
# 6. simulate_delays is forwarded to DeterministicAgent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simulate_delays_forwarded_to_agent():
    """simulate_delays=True on the runner must be forwarded to DeterministicAgent."""
    runner = _make_runner(simulate_delays=True)

    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=dict(_SUCCESS_RESULT))

    with (
        patch("chaos_engine.simulation.runner.ChaosProxy"),
        patch("chaos_engine.simulation.runner.CircuitBreakerProxy"),
        patch("chaos_engine.simulation.runner.DeterministicAgent", return_value=mock_agent_instance) as MockAgent,
    ):
        await runner.run_experiment(agent_type="baseline", failure_rate=0.0, seed=0)

    _, kwargs = MockAgent.call_args
    assert kwargs["simulate_delays"] is True


# ---------------------------------------------------------------------------
# 7. Failure result is propagated correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failure_result_propagated():
    """If the agent returns a failure, run_experiment must return it faithfully."""
    runner = _make_runner()

    mock_agent_instance = MagicMock()
    mock_agent_instance.run = AsyncMock(return_value=dict(_FAILURE_RESULT))

    with (
        patch("chaos_engine.simulation.runner.ChaosProxy"),
        patch("chaos_engine.simulation.runner.CircuitBreakerProxy"),
        patch("chaos_engine.simulation.runner.DeterministicAgent", return_value=mock_agent_instance),
    ):
        result = await runner.run_experiment(agent_type="baseline", failure_rate=1.0, seed=0)

    assert result["status"] == "failure"
    assert result["failed_at"] == "find_pets_by_status"
