"""
src/chaos_playbook_engine/agents/test_agent_adk_v3.py

TestAgent v3: CORRECTAMENTE REFACTORED CON ADK FRAMEWORK

Pattern learned from order_agent_llm.py:
- ✅ LlmAgent - specialized agent class
- ✅ Tools are SYNC functions with type hints
- ✅ generate_content() es SYNC - NO USAR AWAIT
- ✅ Estructura clara: herramientas + agentes + runner
- ✅ InMemoryRunner para ejecución
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import time

# ADK imports - CORRECTO segun patrón de order_agent_llm.py
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner

logger = logging.getLogger(__name__)


@dataclass
class TestAgentMetrics:
    """Metrics for test execution."""
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    total_attempts: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    tests_with_llm_reasoning: int = 0
    
    @property
    def success_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return self.passed / self.total_tests
    
    @property
    def avg_attempts_per_test(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return self.total_attempts / self.total_tests
    
    @property
    def llm_participation_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return self.tests_with_llm_reasoning / self.total_tests


# =====================================================
# STEP 1: DEFINE SYNC TOOLS WITH TYPE HINTS
# =====================================================

def decide_retry_tool(
    error_code: int,
    attempt: int,
    max_retries: int,
    strategy_action: str,
) -> dict:
    """
    Tool: Decide if retry using Gemini LLM - SYNC function
    
    Args:
        error_code: HTTP error code
        attempt: Current attempt number
        max_retries: Maximum retries allowed
        strategy_action: Playbook action strategy
    
    Returns:
        Dictionary with retry decision and LLM reasoning
    """
    logger.info(f"   → Tool: LLM deciding retry (attempt {attempt}/{max_retries})")
    
    try:
        # ✅ PATRÓN CORRECTO: create Gemini instance (no global)
        model = Gemini(model_name="gemini-2.5-flash-lite")
        
        # Prompt para Gemini
        prompt = f"""You are deciding whether to retry a failed API call.

Error Code: {error_code}
Attempt: {attempt} of {max_retries}
Playbook Strategy: {strategy_action}

Analyze the error and decide if we should retry.

Respond ONLY with valid JSON (no markdown, no code blocks):
{{
    "should_retry": true or false,
    "reasoning": "brief reasoning",
    "confidence": 0.5,
    "error_type": "transient or permanent"
}}"""
        
        logger.debug(f"   → Calling Gemini LLM for reasoning...")
        
        # ✅ CRÍTICO: generate_content() es SYNC - NO USAR AWAIT
        # Este es el patrón correcto del ADK Framework
        response = model.generate_content(prompt)
        
        logger.debug(f"   ← Gemini response received")
        
        # Parsear respuesta
        response_text = response.text.strip()
        
        # Limpiar markdown si viene
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        result_json = json.loads(response_text)
        
        # Devolver decisión
        decision = {
            "action": "retry" if result_json.get("should_retry", False) else "fail",
            "reason": result_json.get("reasoning", "No reasoning"),
            "confidence": result_json.get("confidence", 0.5),
            "error_type": result_json.get("error_type", "unknown"),
            "llm_reasoning": result_json,
            "llm_called": True,
        }
        
        logger.info(f"   LLM Decision: {decision['action']}")
        logger.info(f"   LLM Reasoning: {decision['reason']}")
        
        return decision
    
    except Exception as e:
        logger.error(f"   ❌ Gemini call failed: {e}")
        
        # Fallback a heurística
        logger.info(f"   Fallback: Using heuristic")
        should_retry = (
            error_code != 400 and
            error_code != 422 and
            attempt < max_retries
        )
        
        return {
            "action": "retry" if should_retry else "fail",
            "reason": f"Fallback heuristic",
            "confidence": 0.5,
            "error_type": "unknown",
            "llm_reasoning": None,
            "llm_called": False,
        }


# =====================================================
# STEP 2: MAIN TEST AGENT CLASS
# =====================================================

class TestAgentADK:
    """
    TestAgent v3: Real LLM Reasoning with Gemini - ADK Framework Correct Usage
    
    Pattern based on order_agent_llm.py
    - Uses sync tools with type hints
    - No global Gemini instance
    - Clean separation of concerns
    """
    
    def __init__(
        self,
        chaos_agent_func: Callable,
        playbook: Dict[str, Any],
        llm_model: str = "gemini-2.5-flash-lite",
        failure_rate: float = 0.3,
        seed: int = 42,
    ):
        """Initialize TestAgent v3."""
        
        self.chaos_agent_func = chaos_agent_func
        self.playbook = playbook
        self.llm_model = llm_model
        self.failure_rate = failure_rate
        self.seed = seed
        
        self.metrics = TestAgentMetrics()
        
        logger.info("✅ TestAgent v3 (Real LLM Reasoning) initialized")
        logger.info(f"   Model: {llm_model}")
        logger.info(f"   Failure rate: {failure_rate}")
        logger.info(f"   Seed: {seed}")
        logger.info(f"   ⭐ LLM Reasoning: ENABLED (ADK Framework)")
    
    async def _tool_call_operation(
        self,
        operation: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Tool: Llamar operación (con posible caos)."""
        logger.debug(f"→ Tool: call_operation({operation}, {params})")
        self.metrics.tool_calls += 1
        
        result = await self.chaos_agent_func(
            tool_name=operation,
            params=params,
            failure_rate=self.failure_rate,
            seed=self.seed,
        )
        
        logger.debug(f"  Result: status={result.get('status_code')}, chaos={result.get('chaos_injected')}")
        
        return result
    
    async def _tool_check_playbook(
        self,
        error_code: int,
    ) -> Dict[str, Any]:
        """Tool: Consultar playbook para estrategia de error."""
        logger.debug(f"→ Tool: check_playbook(error_code={error_code})")
        self.metrics.tool_calls += 1
        
        # Buscar estrategia en playbook
        error_key = str(error_code)
        
        for procedure in self.playbook.get('procedures', []):
            if error_key in procedure.get('error_codes', []):
                action = procedure['recovery_strategy']
                logger.debug(f"  Strategy found: {action}")
                return {
                    "error_code": error_code,
                    "action": action,
                    "max_retries": 3,
                }
        
        # Default: no retry
        logger.debug(f"  No strategy found for {error_code}")
        return {
            "error_code": error_code,
            "action": "fail",
            "max_retries": 0,
        }
    
    async def _tool_decide_retry(
        self,
        error_code: int,
        attempt: int,
        max_retries: int,
        strategy: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Tool: Decide if retry - LLAMANDO A GEMINI CORRECTAMENTE
        
        ✅ Usa la función SYNC decide_retry_tool
        ✅ Sin await porque generate_content() es SYNC
        """
        self.metrics.llm_calls += 1
        self.metrics.tests_with_llm_reasoning += 1
        
        # ✅ LLAMAR HERRAMIENTA SYNC (sin await)
        decision = decide_retry_tool(
            error_code=error_code,
            attempt=attempt,
            max_retries=max_retries,
            strategy_action=strategy.get('action', 'unknown'),
        )
        
        return decision
    
    async def _tool_apply_backoff(
        self,
        attempt: int,
        base_delay: float = 0.5,
    ) -> Dict[str, Any]:
        """Tool: Aplicar backoff exponencial."""
        logger.debug(f"→ Tool: apply_backoff(attempt={attempt})")
        self.metrics.tool_calls += 1
        
        # Exponential backoff: 0.5s, 1s, 2s, ...
        delay = base_delay * (2 ** (attempt - 1))
        delay = min(delay, 10)  # Cap at 10 seconds
        
        logger.info(f"   Applying backoff: {delay:.2f} seconds")
        await asyncio.sleep(delay)
        
        return {"status": "ok", "delay_applied": delay}
    
    async def run_test_suite(self, tests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ejecutar suite de tests."""
        logger.info(f"🚀 Running {len(tests)} tests with TestAgent v3")
        
        results = []
        self.metrics.total_tests = len(tests)
        
        for i, test_spec in enumerate(tests, 1):
            test_id = test_spec.get('test_id', f'test_{i}')
            operation = test_spec.get('operation', 'unknown')
            params = test_spec.get('params', {})
            
            logger.info(f"\n   [{i}/{len(tests)}] {test_id}")
            
            result = await self._run_single_test(test_id, operation, params)
            results.append(result)
            
            if result.get('ok'):
                self.metrics.passed += 1
            else:
                self.metrics.failed += 1
        
        return results
    
    async def _run_single_test(
        self,
        test_id: str,
        operation: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Ejecutar un test individual con retry logic."""
        attempt = 0
        max_retries = 3
        
        while attempt < max_retries:
            attempt += 1
            self.metrics.total_attempts += 1
            
            logger.debug(f"🧪 Running test: {test_id} (attempt {attempt})")
            
            # Llamar operación
            result = await self._tool_call_operation(operation, params)
            
            status_code = result.get('status_code', 500)
            error = result.get('error')
            
            if status_code == 200:
                # Éxito
                logger.info(f"   ✅ Success (attempt {attempt})")
                return {
                    'test_id': test_id,
                    'operation': operation,
                    'ok': True,
                    'attempts': attempt,
                    'final_status': status_code,
                }
            
            # Error - check playbook
            logger.info(f"   ❌ Error {status_code} (attempt {attempt})")
            
            strategy = await self._tool_check_playbook(status_code)
            
            # ✅ SIEMPRE llamar a Gemini
            decision = await self._tool_decide_retry(
                error_code=status_code,
                attempt=attempt,
                max_retries=max_retries,
                strategy=strategy,
            )
            
            if decision.get('action') != 'retry' or attempt >= max_retries:
                # Gemini decided not to retry o max retries reached
                logger.info(f"   Final: {decision.get('action')}")
                return {
                    'test_id': test_id,
                    'operation': operation,
                    'ok': False,
                    'attempts': attempt,
                    'final_status': status_code,
                    'error': error,
                    'reason': decision.get('action'),
                    'decision': decision,
                }
            
            # Apply backoff
            logger.info(f"   Decision: retry")
            await self._tool_apply_backoff(attempt)
        
        # Max retries reached
        return {
            'test_id': test_id,
            'operation': operation,
            'ok': False,
            'attempts': attempt,
            'reason': 'max_retries_exceeded',
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retornar métricas de ejecución."""
        return {
            'total_tests': self.metrics.total_tests,
            'passed': self.metrics.passed,
            'failed': self.metrics.failed,
            'success_rate': self.metrics.success_rate,
            'total_attempts': self.metrics.total_attempts,
            'avg_attempts_per_test': self.metrics.avg_attempts_per_test,
            'llm_calls': self.metrics.llm_calls,
            'tool_calls': self.metrics.tool_calls,
            'tests_with_llm_reasoning': self.metrics.tests_with_llm_reasoning,
            'llm_participation_rate': self.metrics.llm_participation_rate,
        }
