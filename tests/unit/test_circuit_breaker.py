from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import pytest

from chaos_engine.core.resilience import CircuitBreakerProxy


# ---------------------------------------------------------------------------
# Inline mock executor — defines Executor protocol without importing mocks.py
# ---------------------------------------------------------------------------

class MockExecutor:
    """Deterministic test double that satisfies the Executor protocol."""

    def __init__(self, responses: List[Dict[str, Any]]):
        self.responses = list(responses)
        self.call_count = 0

    async def send_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_body: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        self.call_count += 1
        if self.responses:
            return self.responses.pop(0)
        return {"status": "success", "code": 200, "data": {}}

    def calculate_jittered_backoff(self, seconds: float) -> float:
        return seconds * 2  # distinct from identity so delegation is verifiable


# ---------------------------------------------------------------------------
# Shared response fixtures
# ---------------------------------------------------------------------------

SUCCESS = {"status": "success", "code": 200, "data": {}}
ERROR_500 = {"status": "error", "code": 500, "message": "Internal Server Error"}


# ---------------------------------------------------------------------------
# 1. Circuit stays CLOSED on success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_circuit_stays_closed_on_success():
    """A successful request must not increment the failure counter."""
    executor = MockExecutor([SUCCESS])
    cb = CircuitBreakerProxy(wrapped_executor=executor, failure_threshold=3, cooldown_seconds=60)

    result = await cb.send_request("GET", "/health")

    assert result["status"] == "success"
    assert cb._failures == 0
    assert cb._is_open is False


# ---------------------------------------------------------------------------
# 2. Circuit opens after N consecutive failures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_circuit_opens_after_threshold_failures():
    """Circuit must open exactly when consecutive failures reach the threshold."""
    threshold = 3
    executor = MockExecutor([ERROR_500] * threshold)
    cb = CircuitBreakerProxy(
        wrapped_executor=executor,
        failure_threshold=threshold,
        cooldown_seconds=60,
    )

    for i in range(1, threshold):
        await cb.send_request("GET", "/api")
        assert cb._is_open is False, f"Circuit opened prematurely after {i} failure(s)"

    # Threshold-th failure must open the circuit
    await cb.send_request("GET", "/api")
    assert cb._is_open is True
    assert cb._failures == threshold


# ---------------------------------------------------------------------------
# 3. Circuit returns 503 while open (during cooldown)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_circuit_blocks_requests_while_open():
    """While the circuit is open and within cooldown, all requests must be blocked."""
    executor = MockExecutor([])  # should never be called
    cb = CircuitBreakerProxy(
        wrapped_executor=executor,
        failure_threshold=1,
        cooldown_seconds=9999,
    )
    # Force circuit open
    cb._is_open = True
    cb._opened_timestamp = time.time()

    result = await cb.send_request("GET", "/api")

    assert result["status"] == "error"
    assert result["code"] == 503
    assert "Circuit Breaker Open" in result["message"]
    # The inner executor must never have been called
    assert executor.call_count == 0


# ---------------------------------------------------------------------------
# 4. Half-open: allows ONE probe request after cooldown expires
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_half_open_allows_probe_after_cooldown():
    """After cooldown, exactly one probe request must be forwarded to the executor."""
    executor = MockExecutor([SUCCESS])
    cb = CircuitBreakerProxy(
        wrapped_executor=executor,
        failure_threshold=1,
        cooldown_seconds=0,  # cooldown already expired
    )
    # Force circuit open with a timestamp in the past
    cb._is_open = True
    cb._opened_timestamp = time.time() - 1

    result = await cb.send_request("GET", "/probe")

    # The probe was forwarded and should have succeeded
    assert result["status"] == "success"
    assert executor.call_count == 1


# ---------------------------------------------------------------------------
# 5. Half-open probe success → circuit CLOSES
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_half_open_probe_success_closes_circuit():
    """A successful probe after cooldown must close the circuit and reset failures."""
    executor = MockExecutor([SUCCESS])
    cb = CircuitBreakerProxy(
        wrapped_executor=executor,
        failure_threshold=1,
        cooldown_seconds=0,
    )
    cb._is_open = True
    cb._opened_timestamp = time.time() - 1

    await cb.send_request("GET", "/probe")

    assert cb._is_open is False
    assert cb._half_open is False
    assert cb._failures == 0


# ---------------------------------------------------------------------------
# 6. Half-open probe failure → circuit REOPENS with fresh cooldown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_half_open_probe_failure_reopens_circuit():
    """A failed probe must reopen the circuit and renew the cooldown timestamp."""
    executor = MockExecutor([ERROR_500])
    cb = CircuitBreakerProxy(
        wrapped_executor=executor,
        failure_threshold=1,
        cooldown_seconds=1,
    )
    cb._is_open = True
    old_timestamp = time.time() - 2  # simulated expired cooldown
    cb._opened_timestamp = old_timestamp

    await cb.send_request("GET", "/probe")

    assert cb._is_open is True
    assert cb._half_open is False
    # Fresh cooldown timestamp must be more recent than the original one
    assert cb._opened_timestamp > old_timestamp


# ---------------------------------------------------------------------------
# 7. Success resets the failure counter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_success_resets_failure_counter():
    """After failures that didn't open the circuit, a success must reset _failures to 0."""
    threshold = 5
    failures_before_success = threshold - 1
    executor = MockExecutor([ERROR_500] * failures_before_success + [SUCCESS])
    cb = CircuitBreakerProxy(
        wrapped_executor=executor,
        failure_threshold=threshold,
        cooldown_seconds=60,
    )

    for _ in range(failures_before_success):
        await cb.send_request("GET", "/api")

    assert cb._failures == failures_before_success
    assert cb._is_open is False

    await cb.send_request("GET", "/api")

    assert cb._failures == 0
    assert cb._is_open is False


# ---------------------------------------------------------------------------
# 8. calculate_jittered_backoff delegates to the wrapped executor
# ---------------------------------------------------------------------------

def test_calculate_jittered_backoff_delegates_to_wrapped_executor():
    """calculate_jittered_backoff must delegate to the wrapped executor's implementation."""
    executor = MockExecutor([])
    cb = CircuitBreakerProxy(wrapped_executor=executor, failure_threshold=3, cooldown_seconds=60)

    result = cb.calculate_jittered_backoff(4.0)

    # MockExecutor doubles the value (seconds * 2), so we can verify delegation
    assert result == pytest.approx(8.0)


# ---------------------------------------------------------------------------
# 9. calculate_jittered_backoff falls back if wrapped executor lacks the method
# ---------------------------------------------------------------------------

def test_calculate_jittered_backoff_fallback_when_method_missing():
    """If the wrapped executor has no calculate_jittered_backoff, return seconds unchanged."""

    class MinimalExecutor:
        """Executor that satisfies only send_request (no backoff method)."""

        async def send_request(self, method, endpoint, params=None, json_body=None):
            return SUCCESS

    cb = CircuitBreakerProxy(
        wrapped_executor=MinimalExecutor(),  # type: ignore[arg-type]
        failure_threshold=3,
        cooldown_seconds=60,
    )
    result = cb.calculate_jittered_backoff(3.5)
    assert result == pytest.approx(3.5)


# ---------------------------------------------------------------------------
# 10. Failure counter increments correctly before threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failure_counter_increments_before_threshold():
    """Each consecutive error must increment _failures by exactly 1."""
    threshold = 5
    executor = MockExecutor([ERROR_500] * (threshold - 1))
    cb = CircuitBreakerProxy(
        wrapped_executor=executor,
        failure_threshold=threshold,
        cooldown_seconds=60,
    )

    for expected_count in range(1, threshold):
        await cb.send_request("GET", "/api")
        assert cb._failures == expected_count
        assert cb._is_open is False


# ---------------------------------------------------------------------------
# 11. Circuit blocked request does NOT call the wrapped executor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_blocked_request_does_not_reach_inner_executor():
    """A blocked (open-circuit) request must never reach the inner executor."""
    executor = MockExecutor([SUCCESS])  # Would succeed if reached
    cb = CircuitBreakerProxy(
        wrapped_executor=executor,
        failure_threshold=1,
        cooldown_seconds=9999,
    )
    cb._is_open = True
    cb._opened_timestamp = time.time()

    await cb.send_request("GET", "/api")

    assert executor.call_count == 0


# ---------------------------------------------------------------------------
# 12. Circuit threshold=1: opens on the very first failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_circuit_opens_on_first_failure_with_threshold_one():
    """With failure_threshold=1, a single error must immediately open the circuit."""
    executor = MockExecutor([ERROR_500])
    cb = CircuitBreakerProxy(
        wrapped_executor=executor,
        failure_threshold=1,
        cooldown_seconds=60,
    )

    await cb.send_request("GET", "/api")

    assert cb._is_open is True
    assert cb._failures == 1
