# Chaos Playbook Engine - Project Summary

> Comprehensive technical summary of the repository architecture, components, and data flow.

**Author:** Alberto Martinez Zurita
**Status:** Phase 6 Complete (Validated)
**Achievement:** Winner of the Google Agentic AI Hackathon (Dec 2025) - Top among 11,000+ projects on Kaggle (1.5M course participants)

---

## 1. What Is It

**Chaos Playbook Engine** is an AgentOps Laboratory that systematically injects chaos into AI agents to discover failure modes and synthesize RAG-based recovery playbooks.

It moved beyond "prompt engineering" to **Parametric Engineering**: by running 18,000 controlled experiments across 9 failure rates, it proved that agents equipped with the Playbook Engine achieve **98% reliability** where standard agents fail (37% at 20% failure rate).

### The Core Thesis

| Metric               | Baseline Agent        | Playbook Agent        | Delta          |
|:---------------------|:----------------------|:----------------------|:---------------|
| Success Rate (20%)   | 37%                   | 98%                   | **+60%**       |
| Data Consistency     | 74%                   | 98%                   | **+24%**       |
| Revenue Recovery     | 40% of orders         | 100% of orders        | **3x**         |

---

## 2. Architecture: Hybrid Deterministic + Probabilistic

The system solves the "Hallucination vs. Reliability" dilemma by decoupling:

- **Deterministic Core** (`src/chaos_engine/simulation/`): Seed-controlled chaos experiments with 100% reproducibility
- **Probabilistic Brain** (`src/chaos_engine/agents/`): Google Gemini 2.5 Flash Lite via ADK `LlmAgent` that retrieves (not invents) recovery strategies from the RAG Playbook

### System Data Flow

```
CLI (run_simulation.py / run_comparison.py)
  |
  v
ParametricABTestRunner (async generator, O(1) memory)
  |
  v
ABTestRunner.run_experiment() -- fresh infra per run
  |
  +---> ChaosProxy (seed-based failure injection)
  |       |
  |       v
  +---> CircuitBreakerProxy (CLOSED -> OPEN -> HALF-OPEN)
  |       |
  |       v
  +---> DeterministicAgent / PetstoreAgent (4-step workflow)
          |
          v
        PlaybookStorage.resolve_strategy() (JSON RAG lookup)
          |
          v
        Retry with exponential/linear backoff + jitter
```

---

## 3. Directory Structure (src-layout)

```
chaos-playbook-engine/
+-- src/chaos_engine/         # LOGIC: Core business logic package
|   +-- agents/               # Agent implementations (LLM + Deterministic)
|   +-- chaos/                # Failure injection (ChaosProxy, ChaosConfig)
|   +-- core/                 # Infrastructure (Config, Logging, Resilience, PlaybookStorage)
|   +-- simulation/           # Parametric execution engine (ABTestRunner, ParametricRunner)
|   +-- reporting/            # Dashboard generation (Plotly HTML), MetricsAggregator
|   +-- evaluation/           # Semantic evaluation runner (Golden Dataset)
|   +-- tools/                # Thin tool wrappers (Petstore API, Playbook CRUD)
+-- cli/                      # INTERFACE: 10 executable entry points
+-- config/                   # CONFIG: dev.yaml (mock), prod.yaml (real)
+-- assets/                   # DATA: Playbooks, scenarios, knowledge base, OpenAPI spec
+-- tests/                    # GUARDRAILS: Unit + integration tests
+-- reports/                  # RUNTIME: Experiment outputs, dashboards, CSVs
+-- docs/                     # DOCUMENTATION: Architecture, guides, ADRs
```

---

## 4. Core Components

### 4.1 Agents (`src/chaos_engine/agents/`)

| Component              | File                  | Purpose                                              |
|:-----------------------|:----------------------|:-----------------------------------------------------|
| **PetstoreAgent**      | `petstore.py`         | LLM-based agent (Gemini 2.5 Flash) with full DI. Uses ADK `LlmAgent` + `InMemoryRunner`. Strict 4-step workflow with playbook-driven error recovery. |
| **DeterministicAgent** | `deterministic.py`    | Non-LLM workflow engine for parametric simulation. Eliminates LLM variance. Same 4-step workflow, playbook-driven recovery, no API key required. |
| **OrderAgent**         | `order_agent.py`      | Legacy (Phase 3). Superseded by PetstoreAgent.       |
| **OrderOrchestrator**  | `order_orchestrator.py` | Legacy (Phase 3). E-commerce orchestrator.          |

**The 4-Step Workflow:**
1. `GET /store/inventory` - Check stock levels
2. `GET /pet/findByStatus?status=available` - Find available pets
3. `POST /store/order` - Place order (petId, quantity)
4. `PUT /pet` - Update pet status to "sold"

### 4.2 Chaos Layer (`src/chaos_engine/chaos/`)

| Component        | File         | Purpose                                              |
|:-----------------|:-------------|:-----------------------------------------------------|
| **ChaosConfig**  | `config.py`  | Dataclass with failure_rate, failure_type, seed. `should_inject_failure()` uses seeded RNG for deterministic decisions. |
| **ChaosProxy**   | `proxy.py`   | HTTP middleware. Intercepts `send_request()`, decides failure via `random.Random(seed)`. Supports mock mode + real API (Petstore v3). Zero-trust input validation. |

### 4.3 Core Infrastructure (`src/chaos_engine/core/`)

| Component                | File                  | Purpose                                              |
|:-------------------------|:----------------------|:-----------------------------------------------------|
| **ConfigLoader**         | `config.py`           | YAML config loader (dev/prod) with env var enrichment |
| **setup_logger()**       | `logging.py`          | Centralized logging (anti-duplication pattern)        |
| **PlaybookStorage**      | `playbook_storage.py` | Async JSON-based RAG. `resolve_strategy(tool, code)` with fallback to default. Thread-safe via `asyncio.Lock`. |
| **CircuitBreakerProxy**  | `resilience.py`       | SRE Circuit Breaker: CLOSED -> OPEN (after 5 fails) -> HALF-OPEN (cooldown). Wraps ChaosProxy. Implements `Executor` Protocol. |

### 4.4 Simulation Engine (`src/chaos_engine/simulation/`)

| Component                  | File            | Purpose                                              |
|:---------------------------|:----------------|:-----------------------------------------------------|
| **ABTestRunner**           | `runner.py`     | Single experiment orchestrator. Creates fresh ChaosProxy + CircuitBreaker + DeterministicAgent per run (no state leakage). |
| **ParametricABTestRunner** | `parametric.py` | Multi-rate orchestrator (10K+ experiments). Async generator + streaming CSV write = O(1) memory. Generates `raw_results.csv` + `aggregated_metrics.json`. |

### 4.5 Reporting (`src/chaos_engine/reporting/`)

| Component              | File                   | Purpose                                              |
|:-----------------------|:-----------------------|:-----------------------------------------------------|
| **Dashboard**          | `dashboard.py`         | Interactive HTML dashboard (Plotly) from aggregated metrics |
| **MetricsAggregator**  | `aggregate_metrics.py` | A/B statistics: success rate, consistency rate, latency (p50/p95/p99). Validation criteria: Metric-001 (success +20%), Metric-002 (consistency >= baseline), Metric-003 (latency < 200%). |

### 4.6 CLI Entry Points (`cli/`)

| Script                         | Purpose                                              |
|:-------------------------------|:-----------------------------------------------------|
| `run_simulation.py`            | Main parametric simulation (DeterministicAgent)       |
| `run_comparison.py`            | A/B test two LLM agents (PetstoreAgent) with different playbooks |
| `run_evaluation.py`            | Semantic QA suite against golden dataset              |
| `run_training.py`              | Train agent and create a playbook                     |
| `run_scenario.py`              | Run a predefined chaos scenario from JSON             |
| `generate_report.py`           | Generate markdown report from results                 |
| `generate_parametric_report.py`| Generate parametric report                            |
| `generate_parametric_plots.py` | Generate plots (matplotlib/seaborn)                   |
| `run_comparison_evaluation.py` | Combined comparison + evaluation                      |
| `run_evaluation_showcase.py`   | Showcase evaluation run                               |

---

## 5. Data Assets (`assets/`)

| Asset                           | Purpose                                              |
|:--------------------------------|:-----------------------------------------------------|
| `playbooks/baseline.json`       | No resilience (fail_fast on all errors)               |
| `playbooks/training.json`       | Full recovery matrix per tool + error code (retry_exponential_backoff, wait_and_retry, etc.) |
| `knowledge_base/http_error_codes.json` | HTTP error definitions (loaded by ChaosProxy)  |
| `scenarios/*.json`              | Predefined chaos test scenario definitions            |
| `evaluations/test_suite.json`   | Golden test cases for QA validation                   |
| `specs/petstore3_openapi.json`  | OpenAPI spec for Petstore v3 (reference)              |

---

## 6. Design Patterns

| Pattern                  | Location                      | Purpose                                              |
|:-------------------------|:------------------------------|:-----------------------------------------------------|
| **Dependency Injection** | All agents, CLI composition   | Decouple agents from network/chaos layer              |
| **Protocol (Duck Typing)** | `Executor`, `ToolExecutor`  | Runtime-checkable interfaces, no ABC complexity       |
| **Circuit Breaker**      | `CircuitBreakerProxy`         | Prevent cascading failures (SRE)                      |
| **Strategy Pattern**     | Playbook JSON                 | Encapsulate recovery algorithms                       |
| **Generator Streaming**  | `ParametricABTestRunner`      | O(1) memory for 10K+ experiments (GreenOps)           |
| **Composition Root**     | `cli/run_comparison.py`       | Manual DI object graph construction                   |
| **Proxy/Middleware**     | `ChaosProxy`, `CircuitBreakerProxy` | Intercept and wrap tool execution              |
| **Seed Determinism**     | `ChaosConfig`, `ChaosProxy`  | 100% reproducible chaos via `random.Random(seed)`     |

---

## 7. Quality Pillars

| Pillar                        | Implementation                                       |
|:------------------------------|:-----------------------------------------------------|
| **I. Cognitive Simplicity**   | Guard clauses, <8 complexity per function, flat logic |
| **II. Type Safety**           | 100% strict typing, `Protocol`, `TypedDict`, no `Any` |
| **III. Modularity & DI**      | src-layout, injected dependencies, no hardcoded paths |
| **IV. SRE & Reliability**     | Circuit breaker, jittered backoff, seed determinism   |
| **V. Security (Zero Trust)**  | Input validation (JSON ID type check)                 |
| **VI. GreenOps**              | Generators, streaming CSV, O(1) memory                |
| **VII. Observability**        | Centralized logging, structured outputs, debug modes  |

---

## 8. Technology Stack

- **Language:** Python 3.11
- **Agent Framework:** Google ADK (Agent Development Kit) with eval support
- **LLM:** Gemini 2.5 Flash Lite (via Google ADK)
- **Dependency Management:** Poetry
- **Visualization:** Plotly (HTML dashboards), matplotlib, seaborn
- **Testing:** pytest (asyncio), mypy (strict), black, ruff, isort
- **HTTP Client:** httpx (async)
- **Config:** Pydantic Settings, python-dotenv, YAML

---

## 9. Validated Results

**18,000 parametric experiments** across 9 failure rates (0%-30%):

| Failure Rate | Baseline | Playbook | Improvement |
|:-------------|:---------|:---------|:------------|
| 0%           | 100.0%   | 100.0%   | +0.0%       |
| 1%           | 95.4%    | 100.0%   | +4.6%       |
| 3%           | 88.9%    | 100.0%   | +11.1%      |
| 5%           | 80.9%    | 100.0%   | +19.1%      |
| 10%          | 61.1%    | 99.8%    | +38.7%      |
| 15%          | 50.3%    | 98.5%    | +48.2%      |
| 20%          | 37.2%    | 97.0%    | +59.8%      |

Confidence Level: 95% (p < 0.01). Validated with 1,800 parametric + 280 real experiments without memory leaks or race conditions.

---

## 10. Evolution Roadmap

| Phase     | Goal                          | Status              |
|:----------|:------------------------------|:--------------------|
| Phase 5   | Evidence Base (Parametric)    | Done                |
| Phase 6   | Gemini 2.5 + Real Comparison  | Done                |
| Phase 7   | Cloud Run + Real APIs         | Planned             |
| Phase 8   | PlaybookOps (CI/CD lifecycle) | Planned             |
| Phase 8b  | Triple-Agent Comparison Lab   | Planned             |
| Phase 9   | Agent Judge (Auto-synthesis)  | Planned             |
| Phase 10  | Prompt Science (Parametric)   | Planned             |

See [INNOVATION.md](./INNOVATION.md) for the full strategic vision across 5 horizons.
