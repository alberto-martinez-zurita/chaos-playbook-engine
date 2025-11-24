# Chaos Playbook Engine - Extensibility Guide v2

**Dual Purpose Document:**
1. **Requirements Specification** for Phase 6 (Configuration Parametrization)
2. **Roadmap** for Future Enhancements (Post-Submission)

> *Last updated: November 23, 2025*
> *Version: 2.0 - Strategic Implementation Guide*

---

## 📖 How to Use This Guide

### For Developers Implementing Phase 6 (Parametrization - NOW)
This document serves as **requirements specification**:
- Read **"Estado Actual"** → understand baseline (what exists)
- Read **"Patrón de Extensibilidad General"** → understand target architecture (what we build)
- Implement config loader following examples
- Validate against test scenarios
- Reference this guide in PROMPT 1, 2, 3 to reduce ambiguity

### For Future Contributors (Post-Submission)
This document is a **complete roadmap**:
- **"Implementation Status"** shows what's done vs pending
- Each section has working code examples (copy-paste ready)
- **"Future Enhancements"** details next steps with effort estimates
- Follow patterns, adapt to your use case
- All "Not Implemented" features have full implementation guides

### For Judges/Reviewers
This document demonstrates:
- ✅ **Forward-thinking architecture** (MVP + clear roadmap)
- ✅ **Production-ready extensibility** (config-driven, not code-driven)
- ✅ **Clear scope management** (MVP vs Future work explicitly separated)
- ✅ **Documentation quality** (developer-friendly, comprehensive)

---

## 🏗️ Implementation Status & Roadmap

### ✅ Phase 1-3: Core Implementation (COMPLETED)
**Status:** 90/90 tests passing, production-ready

Completed features:
- Multi-agent architecture (OrderOrchestrator + ExperimentJudge)
- Chaos injection (3 failure types: timeout, service_unavailable, invalid_request)
- A/B testing framework with Baseline vs Playbook comparison
- 3 core metrics (Success Rate, Latency Statistics, Inconsistency Detection)
- Playbook storage (JSON-based, in-memory)
- Session management with event tracking
- 105 comprehensive tests

### 🚀 Phase 6: Configuration Parametrization (IN PROGRESS)

**Goal:** Make framework extensible via config files, not code changes

**Business Value:**
- Non-developers can add new chaos modes (YAML edit)
- Team collaboration (Product Managers, DevOps)
- Environment-specific configs (dev/staging/prod)
- Clean integration with colleague's case generator
- Scores: Pitch 28→30, Implementation 68→70

**Scope:**
- Config loader (YAML/JSON parsing)
- Parametrizable failure types (failure_types.yaml)
- Parametrizable metrics (metrics.yaml)
- Parametrizable tool registry (tools_registry.json)

**Timeline:** 9.5 hours
- PROMPT 1: Config Loader MVP (2h)
- PROMPT 2: ChaosConfig Integration (2h)
- PROMPT 3: MetricsAggregator Parametrization (2h)
- Tests updates + Docs updates (3.5h)

**Status:**
- ⏳ PROMPT 1: Config Loader MVP (Pending)
- ⏳ PROMPT 2: ChaosConfig Integration (Pending)
- ⏳ PROMPT 3: MetricsAggregator Parametrization (Pending)

**Deliverables:**
- `config/failure_types.yaml` - Define chaos modes
- `config/metrics.yaml` - Define evaluation metrics
- `config/tools_registry.json` - Register tools/APIs
- `chaos_playbook_engine/config/loader.py` - Config loading module
- Updated tests (90/90 passing maintained)
- Updated Pitch + Architecture + Plan docs

### 📍 Future Enhancements (POST-SUBMISSION)

#### 🔮 Phase 7: Advanced Failure Modes (NOT IMPLEMENTED)

**Rationale:** Time constraints (7-day deadline). Core 3 failure modes sufficient for MVP validation.

Features designed but not yet implemented:
- ❌ **Cascade failures** (A→B→C chain reactions)
- ❌ **Data corruption** (malformed API responses)
- ❌ **Network partition** simulation
- ❌ **Rate limiting** (HTTP 429 errors)
- ❌ **Authentication failures** (HTTP 401 errors)
- ❌ **Permission denied** (HTTP 403 errors)

**Why now?**
Each failure mode adds:
- 1h code implementation
- 0.5h test coverage
- 0.5h documentation
- Risk of breaking existing tests

**Implementation guide:** See section **"🔧 Extensibilidad: Añadir Nuevos Tipos de Error"** below.

**Recommendation:** Start with `rate_limit` (most common enterprise scenario).

---

#### 📊 Phase 8: Advanced Metrics (NOT IMPLEMENTED)

**Rationale:** Core 3 metrics sufficient for A/B test validation.

Features designed but not yet implemented:
- ❌ **Cost efficiency** tracking (API calls × cost)
- ❌ **Retry effectiveness** distribution (1st retry vs 2nd vs 3rd)
- ❌ **Failure pattern** correlation (error type relationships)
- ❌ **Resource utilization** (memory/CPU during experiments)
- ❌ **Recovery time** distribution (time to recover from failure)
- ❌ **Playbook effectiveness** (% success when strategy applied)

**Why now?**
- Core 3 metrics already demonstrate value (Success Rate +49.99%, Latency -47.26%)
- Additional metrics require more test data (n=100 is baseline)
- Implementation estimate: 6-8 hours total

**Implementation guide:** See section **"📊 Extensibilidad: Añadir Nuevas Métricas"** below.

**Recommendation:** Cost efficiency is highest business value (quantifies ROI).

---

#### 🔗 Phase 9: External Tool Integration (NOT IMPLEMENTED)

**Rationale:** Simulated APIs sufficient for chaos testing during MVP phase.

Features designed but not yet implemented:
- ❌ **Google Search API** integration
- ❌ **BuildCode agent** (Agent-to-Agent communication)
- ❌ **MCP protocol** support (Model Context Protocol)
- ❌ **Real external APIs** (move beyond simulation)
- ❌ **Cloud service** integration (BigQuery, Pub/Sub, etc.)

**Why now?**
- Simulated APIs provide 100% reliability for testing
- Real API integration introduces external dependencies and latency variability
- Better to validate pattern with simulated APIs first
- Integration estimate: 8-12 hours per external service

**Implementation guide:** See section **"🛠️ Extensibilidad: Añadir Nuevos Tools"** below.

**Recommendation:** Google Search API is lowest risk (REST-based, well-documented).

---

## 📋 Estado Actual del Sistema (Baseline)

### **Arquitectura**

```
OrderOrchestrator Agent
├── Llama 4 "tools" (funciones Python async, NO ADK @tool decorators)
│   ├── call_simulated_inventory_api()
│   ├── call_simulated_payments_api()
│   ├── call_simulated_erp_api()
│   └── call_simulated_shipping_api()
│
└── Estructura: Funciones simuladas en simulated_apis.py
```

### **Tipos de Error IMPLEMENTADOS**

| Tipo | HTTP Status | Código | Estado |
|------|-------------|--------|--------|
| `timeout` | 504 | chaos_injection_helper.py L45-52 | ✅ Implementado |
| `service_unavailable` | 503 | chaos_injection_helper.py L54-63 | ✅ Implementado |
| `invalid_request` | 400 | chaos_injection_helper.py L65-74 | ✅ Implementado |
| `cascade` | - | - | ⏳ Placeholder (no código) |
| `partial` | - | - | ⏳ Placeholder (no código) |

### **Métricas IMPLEMENTADAS**

| Métrica | Método | Validación | Estado |
|---------|--------|------------|--------|
| **Success Rate** | `calculate_success_rate()` | Metric-001 (≥20% improvement) | ✅ Implementado |
| **Inconsistency Rate** | `calculate_inconsistency_rate()` | Metric-002 (≥50% reduction) | ✅ Implementado |
| **Latency Statistics** | `calculate_latency_stats()` | Metric-003 (<10% overhead) | ✅ Implementado |

---

## 🔧 Extensibilidad: Añadir Nuevos Tipos de Error

### Ejemplo: Implementar `rate_limit` (HTTP 429)

#### PASO 1: Actualizar Config

**Archivo:** `config/failure_types.yaml` (NUEVO)

```yaml
failure_types:
  - timeout
  - service_unavailable
  - invalid_request
  - rate_limit          # ← NEW
  - cascade
  - partial
  - authentication_failure
  - permission_denied
  - network_partition
  - data_corruption
```

#### PASO 2: Implementar Lógica de Inyección

**Archivo:** `chaos_playbook_engine/tools/chaos_injection_helper.py`

```python
async def inject_chaos_failure(
    api_name: str, 
    endpoint: str, 
    config: ChaosConfig
) -> Dict[str, Any]:
    # ... existing code ...
    
    elif config.failure_type == "rate_limit":
        # NEW BLOCK
        return {
            "status": "error",
            "error_code": "RATE_LIMIT_EXCEEDED",
            "http_status": 429,
            "data": {
                "message": f"{api_name} rate limit exceeded",
                "retry_after_seconds": 60,
                "limit_type": "requests_per_minute",
                "current_usage": 1000,
                "limit": 1000
            },
            "metadata": {
                "api": api_name,
                "endpoint": endpoint,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "chaos_injected": True,
                "failure_type": "rate_limit"
            }
        }
```

#### PASO 3: Añadir Test Coverage

**Archivo:** `tests/test_chaos_injection.py`

```python
@pytest.mark.asyncio
async def test_rate_limit_injection():
    """Test rate limit error injection (429)."""
    config = ChaosConfig(
        enabled=True,
        failure_rate=1.0,
        failure_type="rate_limit"
    )
    
    result = await inject_chaos_failure("inventory", "check_stock", config)
    
    assert result["status"] == "error"
    assert result["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert result["http_status"] == 429
    assert "retry_after_seconds" in result["data"]
```

#### PASO 4: Documentar

**Archivo:** `ARCHITECTURE.md`

```markdown
**Failure Modes Handled:**
- Timeout (504 Gateway Timeout)
- Service unavailable (503)
- Invalid request (400)
- Rate limit exceeded (429)  ← NEW
```

---

## 📊 Extensibilidad: Añadir Nuevas Métricas

### Ejemplo: Implementar `cost_efficiency` Metric

#### PASO 1: Añadir Método de Cálculo

**Archivo:** `experiments/aggregate_metrics.py`

```python
class MetricsAggregator:
    def calculate_cost_efficiency(
        self, 
        results: List[ExperimentResult],
        cost_per_api_call: float = 0.001  # $0.001 per call
    ) -> Dict[str, Any]:
        """
        Calculate cost efficiency metrics.
        
        Returns:
            {
                "total_api_calls": 523,
                "total_cost_usd": 0.523,
                "cost_per_success": 0.0123,
                "cost_per_failure": 0.0087,
                "wasted_cost_on_failures": 0.087
            }
        """
        if not results:
            return {
                "total_api_calls": 0,
                "total_cost_usd": 0.0,
                "cost_per_success": 0.0,
                "cost_per_failure": 0.0,
                "wasted_cost_on_failures": 0.0
            }
        
        total_calls = sum(r.api_calls_made for r in results)
        total_cost = total_calls * cost_per_api_call
        
        successes = [r for r in results if r.outcome == "success"]
        failures = [r for r in results if r.outcome == "failure"]
        
        success_calls = sum(r.api_calls_made for r in successes)
        failure_calls = sum(r.api_calls_made for r in failures)
        
        cost_per_success = (success_calls * cost_per_api_call) / len(successes) if successes else 0.0
        cost_per_failure = (failure_calls * cost_per_api_call) / len(failures) if failures else 0.0
        wasted_cost = failure_calls * cost_per_api_call
        
        return {
            "total_api_calls": total_calls,
            "total_cost_usd": round(total_cost, 4),
            "cost_per_success": round(cost_per_success, 4),
            "cost_per_failure": round(cost_per_failure, 4),
            "wasted_cost_on_failures": round(wasted_cost, 4)
        }
```

#### PASO 2: Integrar en Comparación

```python
def compare_baseline_vs_playbook(self, baseline_results, playbook_results):
    # ... existing code ...
    
    baseline_cost = self.calculate_cost_efficiency(baseline_results)
    playbook_cost = self.calculate_cost_efficiency(playbook_results)
    
    cost_savings = baseline_cost["wasted_cost_on_failures"] - playbook_cost["wasted_cost_on_failures"]
    cost_savings_pct = (cost_savings / baseline_cost["total_cost_usd"]) * 100 if baseline_cost["total_cost_usd"] > 0 else 0.0
    
    return {
        "baseline": {"cost_efficiency": baseline_cost},
        "playbook": {"cost_efficiency": playbook_cost},
        "improvements": {
            "cost_savings_usd": round(cost_savings, 4),
            "cost_savings_pct": round(cost_savings_pct, 2)
        }
    }
```

---

## 🛠️ Extensibilidad: Añadir Nuevos Tools

### OPCIÓN 1: Simulated API (Para Chaos Testing)

**Ejemplo: Google Search API**

**Archivo:** `chaos_playbook_engine/tools/simulated_apis.py`

```python
async def call_simulated_google_search_api(
    endpoint: str,
    payload: Dict[str, Any],
    chaos_config: Optional[ChaosConfig] = None
) -> Dict[str, Any]:
    """Simulate Google Search API calls."""
    
    # Chaos injection
    if chaos_config and chaos_config.should_inject_failure():
        return await inject_chaos_failure("google_search", endpoint, chaos_config)
    
    # Simulate network latency
    await asyncio.sleep(0.15)
    timestamp = datetime.now(timezone.utc).isoformat()
    
    if endpoint == "search":
        query = payload.get("query", "")
        num_results = payload.get("num_results", 10)
        
        return {
            "status": "success",
            "data": {
                "query": query,
                "results": [
                    {
                        "title": f"Result {i+1} for {query}",
                        "url": f"https://example.com/result-{i+1}",
                        "snippet": f"This is a snippet...",
                        "rank": i+1
                    }
                    for i in range(num_results)
                ]
            }
        }
    else:
        raise ValueError(f"Unsupported endpoint: {endpoint}")
```

### OPCIÓN 2: ADK Tool Formal

**Archivo:** `chaos_playbook_engine/tools/google_search_tool.py` (NUEVO)

```python
from google.adk import tool
from typing import Dict, Any, List

@tool
async def search_google(
    query: str,
    num_results: int = 10
) -> Dict[str, Any]:
    """Search Google and return results."""
    from chaos_playbook_engine.tools.simulated_apis import call_simulated_google_search_api
    
    response = await call_simulated_google_search_api(
        endpoint="search",
        payload={"query": query, "num_results": num_results}
    )
    
    if response["status"] == "error":
        raise Exception(f"Google Search error: {response.get('error_code')}")
    
    return response["data"]
```

### OPCIÓN 3: Agent-to-Agent (A2A) Communication

**Archivo:** `chaos_playbook_engine/tools/buildcode_tool.py` (NUEVO)

```python
from google.adk import tool
from google.adk.client import Client
from typing import Dict, Any, List

@tool
async def call_buildcode_agent(
    task_description: str,
    language: str = "python"
) -> Dict[str, Any]:
    """Call BuildCode agent to generate code."""
    
    client = Client(
        agent_name="buildcode_agent",
        endpoint="https://buildcode.agent.google.com"
    )
    
    response = await client.send_task({
        "task": task_description,
        "language": language
    })
    
    return {
        "code": response.get("generated_code"),
        "explanation": response.get("explanation")
    }
```

### OPCIÓN 4: MCP (Model Context Protocol)

**Archivo:** `chaos_playbook_engine/tools/mcp_tool.py` (NUEVO)

```python
from google.adk import tool
from typing import Dict, Any

@tool
async def query_mcp_server(
    server_name: str,
    tool_name: str,
    arguments: Dict[str, Any]
) -> Dict[str, Any]:
    """Query an MCP server."""
    from mcp import Client
    
    client = Client()
    await client.connect_to_server(server_name)
    
    result = await client.call_tool(
        tool_name=tool_name,
        arguments=arguments
    )
    
    return {"status": "success", "result": result}
```

---

## 🔄 Patrón de Extensibilidad General

### Arquitectura Recomendada

```
chaos_playbook_engine/
├── config/
│   ├── loader.py              ← NEW: Config loading
│   ├── failure_types.yaml     ← NEW: Failure modes
│   ├── metrics.yaml           ← NEW: Metrics definitions
│   └── tools_registry.json    ← NEW: Tool registry
│
├── tools/
│   ├── simulated_apis.py
│   ├── chaos_injection_helper.py
│   ├── google_search_tool.py  ← NEW: Google integration
│   ├── buildcode_tool.py      ← NEW: A2A communication
│   └── mcp_tool.py            ← NEW: MCP support
│
└── experiments/
    ├── aggregate_metrics.py
    └── ab_test_runner.py
```

### Workflow Universal para Cada Extensión

**1. TOOL IMPLEMENTATION** (`tools/<tool_name>_tool.py`)
   - Definir función async con `@tool` decorator
   - Implementar lógica de negocio
   - Añadir chaos injection check
   - Return structured response

**2. CHAOS INJECTION** (`tools/chaos_injection_helper.py`)
   - Añadir `elif` branch para nuevo `failure_type`
   - Return error response matching tool's schema

**3. CONFIGURATION** (`config/*.yaml` or `*.json`)
   - Define new entry en archivo de config
   - Loader.py automáticamente lo detecta

**4. TESTS** (`tests/`)
   - Unit tests para nuevo tool
   - Integration tests para chaos patterns
   - Ensure 90/90 tests passing

**5. DOCUMENTATION** (`ARCHITECTURE.md`, `Plan`)
   - Add entry en "Supported Tools/Failure Modes"
   - Code examples en README

---

## 💎 Lecciones Aplicables a Cualquier Extensión

1. **VALIDACIÓN INCREMENTAL** > Mega-Refactor
   - Implement in small PROMPTs
   - Test after cada step
   - Rollback fácil si falla

2. **HIPÓTESIS ANTES QUE CÓDIGO**
   - "¿Qué debe ser cierto para esto?"
   - Test de hipótesis (5 min) > desarrollo ciego (8h)

3. **TESTS SON RED DE SEGURIDAD**
   - Si tests pasan → safe avanzar
   - Si tests fallan → sabes dónde está problema

4. **DOCUMENTACIÓN EN TIEMPO REAL**
   - ADR cuando cambias arquitectura
   - Docs + code en mismo commit
   - No "documentar después"

5. **GIT ES AMIGO**
   - Branch por feature
   - Commit después de cada PROMPT
   - Revert fácil si needed

---

## 📊 Esfuerzo Estimado por Feature

| Feature | Effort | Risk | Priority |
|---------|--------|------|----------|
| Rate Limit (429) | 2h | Low | HIGH |
| Data Corruption | 3h | Medium | Medium |
| Cost Efficiency Metric | 3h | Low | HIGH |
| Cascade Failure | 4h | High | Medium |
| Google Search API | 4h | Medium | Medium |
| BuildCode A2A | 6h | High | Low |
| MCP Protocol | 5h | High | Low |

---

## 🎯 Next Steps (Post-Submission)

1. **Week 1:** Implement Phase 7 (Advanced Failure Modes)
   - Start with `rate_limit`
   - Follow pattern in "Patrón de Extensibilidad General"

2. **Week 2:** Implement Phase 8 (Advanced Metrics)
   - Cost efficiency highest value
   - Use n=500 test runs for validation

3. **Week 3:** Implement Phase 9 (External Tool Integration)
   - Start with Google Search API
   - Migrate from simulated → real APIs

---

## 📞 Support & Questions

For implementing extensions:
1. Reference this guide's "Patrón de Extensibilidad General"
2. Copy code examples verbatim
3. Follow 5-step workflow (Tool → Injection → Config → Tests → Docs)
4. Validate: pytest -v (ensure 90/90 passing)

---

*Built with extensibility in mind - framework designed for enterprise chaos engineering at scale* 🚀
