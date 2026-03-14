# Chaos Playbook Engine - Backlog

> Improvement opportunities and evolution roadmap. Integrates the initial review + CLEAR/OPUS/Multi-Provider audit (42 findings from `docs/AUDIT_CLEAR.md`).

**Last Updated:** 2026-03-13
**Status:** Phase 6 Complete. Planning next evolution.
**Audit Source:** `docs/AUDIT_CLEAR.md` (CLEAR model + ENGINEERING_STANDARDS_OPUS)

---

## Priority Legend

- **P0 - Critical**: Technical debt that blocks evolution or affects correctness
- **P1 - High**: Significant improvements that unlock new capabilities
- **P2 - Medium**: Quality improvements and optimizations
- **P3 - Low**: Nice-to-have refinements

---

## A. Technical Debt & Code Quality (P0-P2)

### A.1 [P0] Streaming Aggregation - Eliminate `all_results_buffer`

**File:** `src/chaos_engine/simulation/parametric.py:67`
**Audit:** CLEAR 10.3 (Media)

The `ParametricABTestRunner` accumulates all results in `all_results_buffer` (O(N) memory), negating the GreenOps generator pattern. Already flagged in `docs/SOFTWARE_QUALITY.md` but not resolved. The GreenOps O(1) claim is partially false.

**Action:** Implement a `StreamingAggregator` class using Welford's algorithm for online mean/variance calculation. Replace `_save_aggregated_metrics(all_results_buffer)` with incremental `aggregator.process(result)` calls inside the generator consumption loop.

**Impact:** Enables scaling to 1M+ experiments without OOM risk. Required for Phase 9 (Agent Judge).

---

### A.2 [P0] Remove Legacy/Dead Code

**Files:**
- `src/chaos_engine/agents/order_agent.py` - Superseded by PetstoreAgent in Phase 6
- `src/chaos_engine/agents/order_orchestrator.py` - Legacy Phase 3 orchestrator
- `src/chaos_engine/simulation/apis.py` - Superseded by real infrastructure stack
**Audit:** CLEAR 1.4, 6.4 (Media)

No `@deprecated` warnings, no markers. Confuses new contributors about the canonical path.

**Action:** Remove or move to `legacy/`. If preserving, add `warnings.warn("deprecated", DeprecationWarning)`.

---

### A.3 [P0] Unify Executor Protocol Definitions

**Files:**
- `src/chaos_engine/core/resilience.py:10` - Defines `Executor` Protocol
- `src/chaos_engine/agents/deterministic.py:18` - Defines identical `Executor` Protocol
- `src/chaos_engine/agents/petstore.py:32` - Defines `ToolExecutor` Protocol (same contract, different name)
**Audit:** CLEAR 1.1 (Alta) - Protocol duplicado en 3 archivos

Three definitions of the same contract is a DRY violation with risk of silent divergence.

**Action:** Create `src/chaos_engine/core/protocols.py` with single `Executor` Protocol. All modules import from one source of truth.

---

### A.4 [P0] Add `from __future__ import annotations` to All Files

**Files:** All 30+ `.py` files in the project
**Audit:** CLEAR 2.1 (Alta)

No file uses `from __future__ import annotations` (PEP 563). Required for forward references and modern typing.

**Action:** Add `from __future__ import annotations` as first import in every `.py` file.

---

### A.5 [P0] Replace `print()` with `logging` in Production Code

**Files & counts:**
- `chaos/config.py` - 15 instances
- `simulation/parametric.py` - 5 instances
- `cli/run_simulation.py` - 6 instances (duplicates logger.info with print)
- `cli/run_comparison.py` - 3 instances
- `tools/petstore_tools.py` - 1 instance
- `reporting/dashboard.py` - 4 instances
**Audit:** CLEAR 3.1 (Alta) - 34 `print()` in production modules

**Action:** Replace all `print()` with `logger.info()` / `logger.debug()`. For `ChaosConfig`, replace `if self.verbose: print(...)` with `logger.debug(...)`.

---

### A.6 [P0] Fix f-strings in Logging Calls

**Files:**
- `chaos/proxy.py:73` - `self.logger.info(f"CHAOS INJECTED: {error_code}...")`
- `core/resilience.py:70` - `self.logger.critical(f"CIRCUIT OPENED...")`
- `simulation/parametric.py:49` - `self.logger.info(f"Starting...")`
- `evaluation/runner.py:65` - `self.logger.info(f"STARTING SUITE: {suite['name']}")`
- `cli/run_comparison.py:87` - `logger.debug(f"Exp {experiment_id}...")`
**Audit:** CLEAR 3.2 (Alta)

f-strings in logging always evaluate interpolation (even when level is disabled) and hinder log aggregation.

**Action:** Replace `logger.info(f"msg {var}")` with `logger.info("msg %s", var)` throughout.

---

### A.7 [P0] Fix `raise` Without `from exc` (Lost Causality)

**Files:**
- `agents/petstore.py:241` - `except Exception as e: return {...}` swallows exception without traceback
- `core/config.py:68` - `raise FileNotFoundError(...)` without `from` context
**Audit:** CLEAR 3.3 (Alta)

Missing `raise X from exc` breaks the causality chain. In petstore.py:241, the exception is silently swallowed.

**Action:** Add `logger.exception("Runner error")` before returns in except blocks. Use `raise X from exc` where re-raising. At minimum `logger.error("...", exc_info=True)`.

---

### A.8 [P1] Define TypedDict for All Public Return Types

**Files:**
- `agents/petstore.py` - `process_order()` -> `Dict[str, Any]`
- `agents/deterministic.py` - `run()` -> `Dict[str, Any]`
- `simulation/runner.py` - `run_experiment()` -> `Dict[str, Any]`
- `chaos/proxy.py` - `send_request()` -> `Dict[str, Any]`
**Audit:** CLEAR 2.2 (Alta) - `Dict[str, Any]` as return type is equivalent to `Any`

**Action:** Define TypedDict or `@dataclass(frozen=True, slots=True)` for each:
```python
class ExperimentResult(TypedDict):
    status: str
    steps_completed: list[str]
    failed_at: str | None
    duration_ms: float
    retries: int

class ApiResponse(TypedDict):
    status: str
    code: int
    data: dict[str, Any] | None
    message: str | None
```

---

### A.9 [P1] Replace Magic Strings with StrEnum

**Files:**
- `agents/deterministic.py:83,90` - `"success"`, `"failure"`
- `chaos/proxy.py:66-74` - `"error"`, `"success"`
- `core/resilience.py:47,57` - status checks with string literals
- `simulation/parametric.py:153,165` - `"success"`, `"failure"`, `"place_order"`, `"update_pet_status"`
**Audit:** CLEAR 2.3 (Media)

**Action:**
```python
from enum import StrEnum

class ExperimentStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"

class WorkflowStep(StrEnum):
    GET_INVENTORY = "get_inventory"
    FIND_PETS = "find_pets_by_status"
    PLACE_ORDER = "place_order"
    UPDATE_PET = "update_pet_status"
```

---

### A.10 [P1] Fragile Path Resolution via `__file__`

**Files:**
- `chaos/proxy.py:31-33` - `Path(__file__).parents[3]` for project root
- `core/config.py:30-32` - `current_file.parent.parent.parent.parent` for project root
**Audit:** CLEAR 6.2 (Media), CLEAR 10.5

Breaks if package is installed via pip or files are moved.

**Action:** Accept paths as constructor parameters (DI), or use `importlib.resources` for package-relative resource access.

---

### A.11 [P1] PetstoreAgent: File Handle Leak

**File:** `src/chaos_engine/agents/petstore.py:75`
**Audit:** CLEAR 10.1 (Media)

`json.load(open(self.playbook_path, 'r', encoding='utf-8'))` opens file without context manager.

**Action:** Use `with open(...) as f: return json.load(f)`.

---

### A.12 [P1] Create Custom Exception Hierarchy

**Audit:** CLEAR 3.4 (Media) - No custom exceptions in the entire project

All errors use generic `Exception`, `ValueError`, `FileNotFoundError`.

**Action:** Create `src/chaos_engine/core/exceptions.py`:
```python
class ChaosEngineError(Exception): ...
class PlaybookError(ChaosEngineError): ...
class ChaosInjectionError(ChaosEngineError): ...
class CircuitBreakerOpenError(ChaosEngineError): ...
class ExperimentError(ChaosEngineError): ...
class ConfigError(ChaosEngineError): ...
```

---

### A.13 [P1] `playbook_tools.py` Bypasses PlaybookStorage Lock

**File:** `src/chaos_engine/tools/playbook_tools.py:74`
**Audit:** CLEAR 1.3 (Media)

`add_scenario_to_playbook()` loads via `storage.load_playbook()` but writes directly to disk with `open()`, bypassing the `asyncio.Lock` in `PlaybookStorage._write_playbook()`. Breaks thread-safety.

**Action:** Use `await storage.save_playbook(playbook)` instead of direct file write.

---

### A.14 [P2] Aggregated Metrics: `std: 0.0` Hardcoded

**Files:**
- `simulation/parametric.py:206` - `"std": 0.0` in calc_stats
- `cli/run_comparison.py:176-180` - `"std": 0.0`
**Audit:** CLEAR 10.2 (Media)

Metrics always report standard deviation = 0. Invalidates statistical claims.

**Action:** Calculate actual standard deviation (binomial for success_rate, sample std for duration).

---

### A.15 [P2] `sys.path` Manipulation Workarounds

**Files:**
- `simulation/parametric.py:20-22` - `sys.path.append()`
- `cli/run_training.py:13-16` - `sys.path.insert(0, str(src_path))`
**Audit:** CLEAR 6.1 (Media), CLEAR 9.1

With proper `src-layout` and `poetry install`, these hacks are unnecessary.

**Action:** Remove fallbacks. Ensure `poetry install` makes package importable. Document in README.

---

### A.16 [P2] ChaosProxy: Incomplete HTTP Method Coverage

**File:** `src/chaos_engine/chaos/proxy.py:83-89`
**Audit:** CLEAR 10.5 (Media)

`send_request()` only handles GET, POST, PUT. DELETE/PATCH silently falls through with no response.

**Action:** Add `else: raise ValueError(f"Unsupported HTTP method: {method}")`.

---

### A.17 [P2] CircuitBreaker: No Half-Open Limit

**File:** `src/chaos_engine/core/resilience.py:48-51`
**Audit:** CLEAR 10.4 (Media)

HALF-OPEN allows unlimited requests. Production circuit breaker should allow exactly one probe.

**Action:** Add `_half_open` state flag. Allow one request. If it fails, reopen with fresh cooldown.

---

### A.18 [P2] Inconsistency Metric Divergence

**Files:** `parametric.py:148` and `aggregate_metrics.py:162`
**Audit:** CLEAR 10.7 (Baja)

Inconsistency calculated differently: parametric uses `failed_at`, MetricsAggregator uses `outcome == "inconsistent"`. These never converge.

**Action:** Align detection. Either DeterministicAgent reports inconsistent outcomes, or MetricsAggregator uses `failed_at` logic.

---

### A.19 [P2] `_enrich_with_env_vars()` Mutates Input + Side Effects

**File:** `src/chaos_engine/core/config.py:79-105`
**Audit:** CLEAR 4.1 (Media), OPUS CQS

Mutates `config` dict in-place AND returns it. Also writes to `os.environ` as side effect (line 94-95). Violates Command-Query Separation.

**Action:** Return new dict `{**config, "api_key": api_key, ...}`. Move `os.environ` setup to separate function.

---

### A.20 [P2] WORKFLOW_STEPS as Mutable List

**File:** `src/chaos_engine/agents/deterministic.py:30-37`
**Audit:** CLEAR 4.2 (Media)

Module-level constant defined as mutable `List`. Can be accidentally modified.

**Action:** Use `tuple` + `Final`: `WORKFLOW_STEPS: Final[tuple[...]] = (...)`

---

### A.21 [P2] `PetstoreAgent.successful_steps` Mutable Instance State

**File:** `src/chaos_engine/agents/petstore.py:71,157`
**Audit:** CLEAR 4.3 (Media)

Mutable set stored as instance attribute, reset between calls. Race condition if used concurrently.

**Action:** Make `successful_steps` local to `process_order()`, not instance attribute.

---

### A.22 [P2] `ChaosConfig` Not Using `slots=True`

**File:** `src/chaos_engine/chaos/config.py:25-26`
**Audit:** CLEAR 2.4 (Media)

`@dataclass` without `slots=True`. Not `frozen` due to `_random_instance`, but should use `slots` for efficiency.

**Action:** `@dataclass(slots=True)`. Document why not frozen.

---

### A.23 [P2] Missing Return Types on Public Functions

**Files:**
- `core/config.py:107` - `_validate_config()` implicit None
- `core/config.py:79` - `_enrich_with_env_vars()` mutates + returns
- `core/logging.py:9` - `setup_logger()` no return type
- `reporting/dashboard.py:264` - `main()` no return type
**Audit:** CLEAR 2.5 (Media)

**Action:** Add explicit return types to all public functions.

---

### A.24 [P2] API Key Copied to Config Dict

**File:** `src/chaos_engine/core/config.py:97`
**Audit:** CLEAR 8.1 (Media)

`config['api_key'] = api_key` copies the API key to a dict that could be logged or serialized.

**Action:** Keep API key only in `os.environ`. Remove from config dict. Access via `os.getenv()` where needed.

---

### A.25 [P2] `.env` File Committed to Repository

**File:** `.env` (350 bytes in repo root)
**Audit:** CLEAR 8.2 (Media)

If contains real API key, this is a credential leak. Only `.env.template` should be committed.

**Action:** Add `.env` to `.gitignore` (already there - verify it wasn't force-added). Remove from git history with `git rm --cached .env` if needed.

---

### A.26 [P2] `run_comparison.py` Loads Config Per Experiment

**File:** `cli/run_comparison.py:47`
**Audit:** CLEAR 10.8 (Baja)

`load_config()` called inside `run_experiment_safe()` - reads YAML + .env on every iteration.

**Action:** Load config once in `run_comparison()`, pass as parameter to `run_experiment_safe()`.

---

### A.27 [P2] `EvaluationRunner` Hot-Swaps Agent Internals

**File:** `src/chaos_engine/evaluation/runner.py:95`
**Audit:** CLEAR 10.6 (Baja)

`self.agent.executor = test_executor` directly accesses and mutates agent internals.

**Action:** Create a new `PetstoreAgent` per test case instead of mutating the existing one.

---

### A.28 [P2] httpx.AsyncClient Created Per Request

**File:** `src/chaos_engine/chaos/proxy.py:83`
**Audit:** CLEAR 5.2 (Media)

`async with httpx.AsyncClient() as client:` creates a new client per request (costly). Uses inline `timeout=10.0`.

**Action:** Inject a reusable `httpx.AsyncClient` with configurable timeout.

---

### A.29 [P2] Domain Directly Imports Google ADK Framework

**Files:**
- `agents/petstore.py:19-21` - `from google.adk.agents import LlmAgent`
- `evaluation/runner.py:16` - `from google.adk.models.google_llm import Gemini`
**Audit:** CLEAR 1.2 (Alta)

Domain core (`agents/`) imports framework implementations directly. If ADK changes, agents must be rewritten.

**Action:** Abstract ADK behind a Protocol/adapter. Agent receives an `AgentRunner` Protocol, not `InMemoryRunner` directly. Long-term item for Phase 7+.

---

### A.30 [P3] Naming Inconsistencies

**Files:**
- `reporting/dashboard.py` - `extract_chart_data()`, `calculate_summary_stats()` are public but helper-only
- `core/config.py:107` - `_validate_config()` private but never called
- `__init__.py` files - Empty, no `__all__` defined
**Audit:** CLEAR 6.3, 6.5 (Baja)

**Action:** Prefix internal helpers with `_`. Remove dead code. Define `__all__` in `__init__.py`.

---

### A.31 [P3] Magic Numbers for Circuit Breaker Config

**Files:**
- `core/resilience.py:22` - default `failure_threshold=5`
- `simulation/runner.py:49` - `failure_threshold=3`
- `cli/run_comparison.py:62-63` - `failure_threshold=3`
- `agents/petstore.py:161` - `temperature=0.0`
**Audit:** CLEAR 6.4 (Baja)

Inconsistent defaults (5 vs 3) and inline magic numbers.

**Action:** Centralize as named constants or config values.

---

### A.32 [P3] `PetstoreAgent.wait_seconds()` Always Sleeps

**File:** `src/chaos_engine/agents/petstore.py:124`
**Audit:** CLEAR 5.1 (Media)

`await asyncio.sleep(jittered_seconds)` always executes, even in simulation mode. `DeterministicAgent` has `simulate_delays` flag but `PetstoreAgent` does not.

**Action:** Add `simulate_delays` flag to `PetstoreAgent` constructor.

---

### A.33 [P3] No Graceful Shutdown in CLI Scripts

**Audit:** CLEAR 5.3 (Baja)

No `signal` handlers for SIGTERM/SIGINT. If a 10K experiment run is interrupted, partial results may be lost.

**Action:** Add signal handler that flushes CSV and saves partial aggregation on interrupt.

---

## B. Testing & Reliability (P0-P2)

### B.1 [P0] Test Coverage for Core Simulation Components

**Audit:** CLEAR 7.1 (Alta) - The workhorse of 18K experiments has zero unit tests

**Missing tests for:**
- `DeterministicAgent` - workflow execution, retry logic, playbook resolution, edge cases
- `ABTestRunner` - experiment orchestration, fresh infra per run
- `ParametricABTestRunner` - generator streaming, CSV writing, aggregation
- `ChaosProxy.send_request()` - mock mode, real API mode, error code injection

**Action:** Add unit tests with mock `Executor`. Verify 4-step workflow, retry with each strategy type, playbook fallback to default. Add integration test for `ABTestRunner` with known seed to verify deterministic output.

---

### B.2 [P2] Integration Test Relies on GOOGLE_API_KEY

**File:** `tests/integration/test_order_agent.py`

The integration test requires a valid API key, making CI/CD impossible without secrets. Also uses legacy `OrderAgent`.

**Action:** Create parallel integration test using `DeterministicAgent` (no API key). Keep LLM test as optional smoke test gated by env var.

---

### B.3 [P1] No CI/CD Pipeline

**Audit:** CLEAR 9.1, 9.2, 9.3 (Media)

No GitHub Actions, no pre-commit hooks. `ruff`, `black`, `isort`, `mypy` are configured in `pyproject.toml` but not enforced.

**Action:** Add GitHub Actions workflow: `poetry install` -> `ruff check` -> `mypy --strict` -> `pytest --cov`. Add pre-commit hooks for ruff + mypy.

---

### B.4 [P2] Tests Don't Use `@pytest.mark.parametrize`

**Files:** `tests/unit/test_chaos_engine.py`, `tests/unit/test_metrics.py`
**Audit:** CLEAR 7.7 (Media)

Repetitive tests with different inputs that should use parametrize.

**Action:** Refactor to `@pytest.mark.parametrize` where applicable.

---

### B.5 [P3] No Property-Based Testing

**Audit:** CLEAR 7.8 (Baja)

Candidates for `hypothesis`:
- `ChaosConfig.should_inject_failure()` with random rates
- `MetricsAggregator.calculate_success_rate()` with generated inputs
- `DeterministicAgent._calculate_delay()` invariants per strategy

---

### B.6 [P3] No Vulnerability Scanning

**Audit:** CLEAR 8.5 (Baja)

No `pip-audit`, `safety`, or `dependabot`. With 30+ dependencies, supply chain risk is real.

**Action:** Add `pip-audit` to CI pipeline. Consider enabling Dependabot on GitHub.

---

### B.7 [P3] No `__main__.py` Entry Point

**Audit:** CLEAR 9.3 (Baja)

No `python -m chaos_engine` support. Only loose CLI scripts.

**Action:** Add `src/chaos_engine/__main__.py` that dispatches to subcommands.

---

## C. Observability & Logging (P1-P2)

### C.1 [P1] Structured Logging (JSON)

**Audit:** CLEAR 3.5 (Media)

Logs are plain text without structure. No correlation IDs, no parseable fields. Blocks Phase 7 (production) and Phase 9 (observability ingestion).

**Action:** Migrate to structured logging (`structlog` or stdlib with `dictConfig`):
```python
logger.info("experiment_completed", extra={
    "experiment_id": exp_id, "failure_rate": rate,
    "outcome": outcome, "duration_ms": duration_ms,
})
```

---

### C.2 [P2] Logging Config via `dictConfig`

**Audit:** CLEAR 10.7 from OPUS

Current `setup_logger()` uses manual handler setup. Production should use `logging.config.dictConfig()`.

**Action:** Replace `setup_logger()` internals with `dictConfig` pattern. Allows JSON/YAML logging config.

---

## D. Evolution Features - Phase 7: Production (P1)

### D.1 [P1] Real API Integration via Executor Protocol

**Vision:** Move from simulation to reality with Cloud Run and live APIs.

**Action:**
1. Create `src/chaos_engine/infrastructure/real_apis.py` implementing `Executor` Protocol with `httpx`
2. Support configurable base URLs via config YAML
3. Add timeout configuration per-endpoint
4. Update `cli/run_comparison.py` composition root to support `--real-mode` flag

---

### D.2 [P1] Containerization (Docker/Cloud Run)

**Action:**
1. Create `Dockerfile` with multi-stage build (Poetry install -> slim runtime)
2. Add `docker-compose.yml` for local development
3. Create Cloud Run deployment config
4. Externalize all config via environment variables (12-Factor)

---

### D.3 [P2] Configuration Validation with Pydantic

**Audit:** CLEAR 2.7

**Action:** Replace raw dict-based config with Pydantic `BaseSettings` models. Validate failure_rates in [0,1], seed positive, paths exist. Fail fast with clear error messages.

---

## E. Evolution Features - Phase 8: PlaybookOps (P1-P2)

### E.1 [P1] Playbook Versioning & Lifecycle

**Vision:** Treat playbooks as software artifacts with CI/CD: Dev -> Lab -> Staging -> Production.

**Action:**
1. Add `version`, `created_at`, `validated_by` metadata to playbook JSON schema
2. Implement `PlaybookRegistry` class that manages multiple versions
3. Add CLI: `cli/promote_playbook.py --from dev --to staging --min-success-rate 0.95`
4. Validation gate: run N experiments before promotion; reject if metrics fail

---

### E.2 [P1] Hot-Swap Playbooks at Runtime

**Vision:** Update playbooks without redeploying the agent.

**Action:**
1. Add file watcher to `PlaybookStorage` that reloads on change
2. Add HTTP endpoint (FastAPI) for playbook CRUD in production mode
3. Implement optimistic locking to prevent concurrent edits

---

### E.3 [P2] Triple-Agent Comparison Lab

**Vision:** Adversarial tournament between Aggressive, Balanced, and Conservative configs.

**Action:**
1. Extend `ParametricABTestRunner` to support N agent types (not just baseline/playbook)
2. Create playbook variants: `aggressive.json`, `conservative.json`
3. Add ranking/leaderboard to dashboard output
4. Auto-promote winner to "current best"

---

## F. Evolution Features - Phase 9: Agent Judge (P2)

### F.1 [P2] Autonomous Playbook Synthesis

**Vision:** Observer agent (Gemini) analyzes logs and writes recovery strategies.

**Action:**
1. Implement `PlaybookWriterAgent` (ADK LlmAgent) that ingests `raw_results.csv`
2. Agent outputs candidate JSON playbook entries
3. Auto-validation: run parametric test; commit only if success rate improves
4. Safety: require human approval before production promotion

---

### F.2 [P2] Production Observability Ingestion

**Vision:** Import Cloud Logging traces to replay real outages.

**Action:**
1. Create `ingestion/cloud_logging.py` for Google Cloud Logging API
2. Convert logs to scenario format (`assets/scenarios/`)
3. Enable "Digital Twin" mode: replay exact production failure sequences

---

## G. Evolution Features - Phase 10: Prompt Science (P2)

### G.1 [P2] Parametric Prompt Testing

**Vision:** A/B test prompts against same chaos to discover optimal instruction patterns.

**Action:**
1. Refactor `ParametricABTestRunner` to accept `prompts: List[str]`
2. Fixed seed: every prompt faces exact same failure sequence
3. Output: prompt leaderboard ranked by success rate, latency, consistency

---

### G.2 [P2] Prompt Mutation & Evolution

**Vision:** Genetic algorithm approach to prompt optimization.

**Action:**
1. Base prompt + N mutations (LLM-assisted)
2. Parametric test each mutation
3. Select top performers, cross-breed, iterate until convergence

---

## H. Infrastructure & Developer Experience (P2-P3)

### H.1 [P3] CLI Unification

**Action:** Consolidate 10 CLI scripts into single `chaos-engine` CLI with subcommands via `click` or `typer`:
```
chaos-engine simulate --failure-rates 0.1 0.2 --experiments 50
chaos-engine compare --agent-a baseline --agent-b training
chaos-engine evaluate --suite test_suite.json
chaos-engine judge --input raw_results.csv
```

---

### H.2 [P3] Dashboard Improvements

**Action:**
1. Time-series view (experiment execution timeline)
2. Drill-down per failure rate
3. Export to PDF
4. Comparison across multiple runs (trend analysis)

---

### H.3 [P3] MCP/A2A Chaos Support (Horizon 4)

**Vision:** Apply chaos injection to MCP tool calls and Agent-to-Agent communication.

**Action:**
1. Implement `MCPChaosProxy` wrapping MCP server connections
2. Implement `A2AChaosProxy` for agent-to-agent calls
3. Playbook strategies for "Tool Unavailable", "Context Window Exceeded", "Agent Timeout"

---

## Summary Matrix

| ID    | Priority | Category         | Effort | Audit Ref   | Unlocks   |
|:------|:---------|:-----------------|:-------|:------------|:----------|
| A.1   | P0       | Tech Debt        | M      | CLEAR 10.3  | Phase 9   |
| A.2   | P0       | Tech Debt        | S      | CLEAR 1.4   | -         |
| A.3   | P0       | Code Quality     | S      | CLEAR 1.1   | -         |
| A.4   | P0       | Code Quality     | S      | CLEAR 2.1   | -         |
| A.5   | P0       | Observability    | M      | CLEAR 3.1   | Phase 7   |
| A.6   | P0       | Observability    | S      | CLEAR 3.2   | -         |
| A.7   | P0       | Exceptions       | S      | CLEAR 3.3   | -         |
| A.8   | P1       | Typing           | M      | CLEAR 2.2   | -         |
| A.9   | P1       | Typing           | M      | CLEAR 2.3   | -         |
| A.10  | P1       | Code Quality     | S      | CLEAR 6.2   | Phase 7   |
| A.11  | P1       | Code Quality     | S      | CLEAR 10.1  | -         |
| A.12  | P1       | Exceptions       | M      | CLEAR 3.4   | Phase 7   |
| A.13  | P1       | Thread Safety    | S      | CLEAR 1.3   | -         |
| A.14  | P2       | Metrics          | S      | CLEAR 10.2  | -         |
| A.15  | P2       | Packaging        | S      | CLEAR 9.1   | -         |
| A.16  | P2       | Code Quality     | S      | CLEAR 10.5  | -         |
| A.17  | P2       | SRE              | S      | CLEAR 10.4  | Phase 7   |
| A.18  | P2       | Metrics          | M      | CLEAR 10.7  | -         |
| A.19  | P2       | Immutability     | S      | CLEAR 4.1   | -         |
| A.20  | P2       | Immutability     | S      | CLEAR 4.2   | -         |
| A.21  | P2       | Immutability     | S      | CLEAR 4.3   | -         |
| A.22  | P2       | Typing           | S      | CLEAR 2.4   | -         |
| A.23  | P2       | Typing           | S      | CLEAR 2.5   | -         |
| A.24  | P2       | Security         | S      | CLEAR 8.1   | -         |
| A.25  | P2       | Security         | S      | CLEAR 8.2   | -         |
| A.26  | P2       | Performance      | S      | CLEAR 10.8  | -         |
| A.27  | P2       | Encapsulation    | S      | CLEAR 10.6  | -         |
| A.28  | P2       | Performance      | S      | CLEAR 5.2   | Phase 7   |
| A.29  | P2       | Architecture     | L      | CLEAR 1.2   | Phase 7+  |
| A.30  | P3       | Naming           | S      | CLEAR 6.3   | -         |
| A.31  | P3       | Constants        | S      | CLEAR 6.4   | -         |
| A.32  | P3       | Concurrency      | S      | CLEAR 5.1   | -         |
| A.33  | P3       | Concurrency      | S      | CLEAR 5.3   | -         |
| B.1   | P0       | Testing          | L      | CLEAR 7.1   | Phase 7,8 |
| B.2   | P2       | Testing          | S      | -           | -         |
| B.3   | P1       | CI/CD            | M      | CLEAR 9.3   | Phase 7   |
| B.4   | P2       | Testing          | S      | CLEAR 7.7   | -         |
| B.5   | P3       | Testing          | M      | CLEAR 7.8   | -         |
| B.6   | P3       | Security         | S      | CLEAR 8.5   | -         |
| B.7   | P3       | Packaging        | S      | CLEAR 9.3   | -         |
| C.1   | P1       | Observability    | M      | CLEAR 3.5   | Phase 7,9 |
| C.2   | P2       | Observability    | S      | OPUS 12     | Phase 7   |
| D.1   | P1       | Phase 7          | L      | -           | Phase 7   |
| D.2   | P1       | Phase 7          | M      | -           | Phase 7   |
| D.3   | P2       | Phase 7          | S      | CLEAR 2.7   | Phase 7   |
| E.1   | P1       | Phase 8          | L      | -           | Phase 8   |
| E.2   | P1       | Phase 8          | M      | -           | Phase 8   |
| E.3   | P2       | Phase 8          | L      | -           | Phase 8   |
| F.1   | P2       | Phase 9          | L      | -           | Phase 9   |
| F.2   | P2       | Phase 9          | L      | -           | Phase 9   |
| G.1   | P2       | Phase 10         | M      | -           | Phase 10  |
| G.2   | P2       | Phase 10         | L      | -           | Phase 10  |
| H.1   | P3       | DX               | M      | -           | -         |
| H.2   | P3       | DX               | M      | -           | -         |
| H.3   | P3       | Horizon 4        | L      | -           | -         |

**Effort:** S = Small (hours), M = Medium (1-3 days), L = Large (1+ week)

**Counts:** P0: 8 | P1: 10 | P2: 24 | P3: 11 | **Total: 53 items**

---

## Recommended Execution Order

### Sprint 0: Quick Wins (< 2 hours, 7 items)
A.3 (unify protocols), A.4 (`__future__` annotations), A.6 (f-strings in logging), A.7 (raise from exc), A.11 (file handle), A.16 (HTTP method guard), A.17 (circuit breaker half-open)

### Sprint 1: Critical Foundation (P0 items)
A.1 (StreamingAggregator), A.2 (remove legacy), A.5 (print -> logging), B.1 (core tests)

### Sprint 2: Type Safety & Contracts
A.8 (TypedDict returns), A.9 (StrEnum), A.10 (path resolution), A.12 (exception hierarchy), A.13 (playbook lock bypass)

### Sprint 3: Testing & CI
B.3 (CI pipeline), B.4 (parametrize), A.14-A.28 (remaining P2 code quality), C.1 (structured logging)

### Sprint 4: Phase 7 - Production
D.1 (real API executor), D.2 (Docker), D.3 (Pydantic config), A.29 (ADK abstraction), C.2 (dictConfig)

### Sprint 5: Phase 8 - PlaybookOps
E.1 (versioning), E.2 (hot-swap), E.3 (triple-agent)

### Sprint 6: Phase 9-10 - Intelligence
F.1 (Agent Judge), F.2 (observability), G.1 (prompt lab)
