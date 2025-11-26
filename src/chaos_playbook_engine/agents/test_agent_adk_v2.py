"""
src/chaos_playbook_engine/agents/test_agent_adk_v3.py

TestAgent con VERDADERO RAZONAMIENTO LLM en _tool_decide_retry

VERSION 3: LLM REASONING REAL

La diferencia crítica:

v2 (Cartón piedra):
    if attempt >= max_retries: return 'fail'
    else: return 'retry'
    ← DECISIÓN HEURÍSTICA, GEMINI NO PARTICIPA

v3 (REAL):
    prompt = f"Error {error_code}, intento {attempt}/{max_retries}. ¿Reintentar?"
    response = await self.model.generate_content(prompt)
    decision = parse(response)
    return decision
    ← GEMINI RAZONA Y DECIDE

"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

# ADK imports - PATH CORRECTO
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini  # ← CORRECTO (google_llm, no googlellm)
from google.adk.tools import ToolContext
from pydantic import Field, ConfigDict

logger = logging.getLogger(__name__)


class TestAgentADK(LlmAgent):
    """
    ADK Agent for testing with chaos engineering - WITH REAL LLM REASONING.
    
    VERSION 3: VERDADERO RAZONAMIENTO CON GEMINI
    
    Diferencia con v2:
    - v2: Heurísticas hardcoded (cartón piedra)
    - v3: Gemini REALMENTE RAZONA en _tool_decide_retry
    
    Flujo:
    1. Test fails con error_code
    2. call _tool_check_playbook → strategy
    3. call _tool_decide_retry → GEMINI RAZONA ← AQUÍ ES DONDE OCURRE LA MAGIA
    4. Gemini genera prompt: "¿Debemos reintentar?"
    5. Gemini genera respuesta JSON con decisión + reasoning
    6. Parsear respuesta y ejecutar decisión
    7. Si retry: apply_backoff y volver al paso 1
    """
    
    # Configuración Pydantic
    model_config = ConfigDict(extra='allow')
    
    # Campos
    chaos_agent_func: Optional[Callable] = Field(default=None)
    playbook: Dict[str, Any] = Field(default_factory=dict)
    failure_rate: float = Field(default=0.3)
    seed: int = Field(default=42)
    test_results: List[Dict[str, Any]] = Field(default_factory=list)
    llm_calls: int = Field(default=0)
    tool_calls: int = Field(default=0)
    
    def __init__(
        self,
        chaos_agent_func: Optional[Callable] = None,
        playbook: Dict[str, Any] = None,
        llm_model: str = "gemini-2.5-flash-lite",
        failure_rate: float = 0.3,
        seed: int = 42,
        **kwargs
    ):
        """Initialize TestAgent with REAL LLM reasoning."""
        
        if playbook is None:
            playbook = {}
        
        # Tools
        tools = [
            self._tool_call_operation,
            self._tool_check_playbook,
            self._tool_decide_retry,
            self._tool_apply_backoff,
        ]
        
        # System instruction
        instruction = """You are a Testing Agent specialized in chaos engineering.

Your objective: Execute tests against APIs and make intelligent decisions about failures.

When a test fails:
1. Always check the playbook for the error code
2. Reason about whether to retry based on:
   - Max retries allowed
   - Backoff strategy
   - Error severity
   - Cumulative failures
3. Decide: retry with backoff, or accept the failure
4. Execute the decision

Always explain your reasoning in detail. Be methodical and deterministic.
Your decisions should be based on:
- Probability of transient vs permanent failures
- Cost-benefit of retrying
- Circuit breaker patterns
"""
        
        # Initialize LlmAgent with Gemini
        super().__init__(
            name="TestAgentADK",
            model=Gemini(
                model=llm_model,
                temperature=0.3  # Low temperature for deterministic decisions
            ),
            instruction=instruction,
            tools=tools,
        )
        
        # Assign fields
        self.chaos_agent_func = chaos_agent_func
        self.playbook = playbook
        self.failure_rate = failure_rate
        self.seed = seed
        self.test_results = []
        self.llm_calls = 0
        self.tool_calls = 0
        
        logger.info(f"✅ TestAgent v3 (Real LLM Reasoning) initialized")
        logger.info(f"   Model: {llm_model}")
        logger.info(f"   Failure rate: {failure_rate}")
        logger.info(f"   Seed: {seed}")
        logger.info(f"   ⭐ LLM Reasoning: ENABLED")
    
    async def run_test(self, test_spec: Dict[str, Any], attempt: int = 1) -> Dict[str, Any]:
        """Run a single test with LLM reasoning."""
        
        logger.info(f"🧪 Running test: {test_spec['test_id']} (attempt {attempt})")
        
        operation_id = test_spec['operation']
        params = test_spec.get('params', {})
        
        # Call operation
        call_result = await self._tool_call_operation(
            operation_id=operation_id,
            params=params
        )
        
        # Check if failed
        if call_result['status_code'] >= 400:
            # Failed - check playbook
            playbook_strategy = await self._tool_check_playbook(
                error_code=call_result['status_code']
            )
            
            # ✅ AQUÍ OCURRE LA MAGIA: LLM RAZONA
            decision = await self._tool_decide_retry(
                error_code=call_result['status_code'],
                attempt=attempt,
                max_retries=playbook_strategy.get('max_retries', 0),
                strategy=playbook_strategy
            )
            
            logger.info(f"   LLM Decision: {decision['action']}")
            if 'llm_reasoning' in decision:
                logger.info(f"   LLM Reasoning: {decision['llm_reasoning']}")
            
            # Execute decision
            if decision['action'] == 'retry':
                backoff = playbook_strategy.get('backoff_seconds', 1) * attempt
                logger.info(f"   Applying backoff: {backoff}s")
                await self._tool_apply_backoff(seconds=backoff)
                
                # Recursive retry
                return await self.run_test(test_spec, attempt=attempt + 1)
            
            else:
                # Accept failure
                return {
                    'test_id': test_spec['test_id'],
                    'operation': operation_id,
                    'status_code': call_result['status_code'],
                    'ok': False,
                    'chaos_injected': call_result.get('chaos_injected', False),
                    'error': call_result.get('error'),
                    'attempts': attempt,
                    'decision': decision,
                    'playbook_used': True,
                    'llm_used': True,  # ← LLM fue usado
                }
        
        # Success
        return {
            'test_id': test_spec['test_id'],
            'operation': operation_id,
            'status_code': call_result['status_code'],
            'ok': True,
            'chaos_injected': call_result.get('chaos_injected', False),
            'error': None,
            'attempts': attempt,
            'decision': {'action': 'success'},
            'playbook_used': False if attempt == 1 else True,
            'llm_used': False if attempt == 1 else True,  # ← LLM usado si hay retries
        }
    
    async def run_test_suite(self, test_suite: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run a suite of tests."""
        
        logger.info(f"🚀 Running {len(test_suite)} tests with TestAgent (LLM Reasoning v3)")
        
        results = []
        for i, test in enumerate(test_suite, 1):
            logger.info(f"\n   [{i}/{len(test_suite)}] {test.get('test_id', f'test_{i}')}")
            result = await self.run_test(test)
            results.append(result)
            self.test_results.append(result)
        
        return results
    
    # ========================================================================
    # TOOLS
    # ========================================================================
    
    async def _tool_call_operation(
        self,
        operation_id: str,
        params: Dict[str, Any],
        toolcontext: Optional[ToolContext] = None
    ) -> Dict[str, Any]:
        """Tool: Call ChaosAgent to execute operation."""
        
        logger.debug(f"   → Tool: calling {operation_id}({params})")
        self.tool_calls += 1
        
        if not self.chaos_agent_func:
            logger.error("❌ ChaosAgent function not set!")
            return {
                "status_code": 500,
                "body": None,
                "error": "ChaosAgent not initialized",
                "chaos_injected": False,
                "attempt_number": 1
            }
        
        try:
            result = await self.chaos_agent_func(
                operation_id=operation_id,
                params=params,
                failure_rate=self.failure_rate,
                seed=self.seed
            )
            
            logger.debug(f"     Result: status={result.get('status_code')}, "
                        f"chaos={result.get('chaos_injected')}")
            
            return result
        
        except Exception as e:
            logger.error(f"❌ ChaosAgent call failed: {e}")
            return {
                "status_code": 500,
                "body": None,
                "error": str(e),
                "chaos_injected": False,
                "attempt_number": 1
            }
    
    async def _tool_check_playbook(
        self,
        error_code: int,
        toolcontext: Optional[ToolContext] = None
    ) -> Dict[str, Any]:
        """Tool: Consult playbook for error handling strategy."""
        
        logger.debug(f"   → Tool: checking playbook for error {error_code}")
        
        for procedure in self.playbook.get('procedures', []):
            if str(procedure.get('error_code', '')) == str(error_code):
                result = {
                    'found': True,
                    'error_code': error_code,
                    'action': procedure.get('action', 'fail'),
                    'max_retries': procedure.get('max_retries', 0),
                    'backoff_seconds': procedure.get('backoff_seconds', 1),
                    'reason': procedure.get('reason', 'No reason provided'),
                }
                logger.debug(f"     Strategy: {result['action']} "
                           f"(max_retries={result['max_retries']})")
                return result
        
        # Not found
        return {
            'found': False,
            'error_code': error_code,
            'action': 'fail',
            'max_retries': 0,
            'reason': 'No strategy in playbook for this error',
        }
    
    async def _tool_decide_retry(
        self,
        error_code: int,
        attempt: int,
        max_retries: int,
        strategy: Dict[str, Any],
        toolcontext: Optional[ToolContext] = None
    ) -> Dict[str, Any]:
        """
        Tool: LLM DECIDES WHETHER TO RETRY - WITH REAL REASONING.
        
        ✅ VERSIÓN 3: GEMINI REALMENTE RAZONA AQUÍ
        
        Este es el punto donde Gemini participa en la decisión,
        NO es una heurística hardcoded.
        """
        
        logger.debug(f"   → Tool: LLM deciding retry (attempt {attempt}/{max_retries})")
        self.llm_calls += 1
        
        # Crear prompt para Gemini
        prompt = f"""
You are a Testing Agent deciding whether to retry a failed API call.

CONTEXT:
- HTTP Error Code: {error_code}
- Current Attempt: {attempt}/{max_retries}
- Playbook Action: {strategy['action']}
- Playbook Reason: {strategy['reason']}
- Backoff Seconds: {strategy['backoff_seconds']}

ANALYSIS:
- Is this a transient error (4xx)?
- Is this a permanent error (5xx)?
- Have we exhausted retries?
- Does the playbook recommend retrying?

YOUR TASK:
Decide whether to retry this test based on:
1. Error code type (transient vs permanent)
2. Remaining retries
3. Playbook strategy
4. Overall test strategy

RESPOND ONLY WITH VALID JSON (no markdown, no explanation):
{{
    "should_retry": true or false,
    "reasoning": "2-3 sentence explanation of your decision",
    "confidence": 0.0 to 1.0,
    "error_type": "transient or permanent"
}}
"""
        
        try:
            # ✅ LLAMAR A GEMINI REALMENTE - AQUÍ ES LA MAGIA
            logger.debug(f"   → Calling Gemini LLM for reasoning...")
            response = await self.model.generate_content(prompt)
            
            result_text = response.text.strip()
            logger.debug(f"   ← Gemini response: {result_text[:100]}...")
            
            # Parsear respuesta JSON
            result_json = json.loads(result_text)
            
            return {
                'action': 'retry' if result_json['should_retry'] else 'fail',
                'reason': result_json['reasoning'],
                'confidence': result_json['confidence'],
                'error_type': result_json.get('error_type', 'unknown'),
                'attempt': attempt,
                'max_retries': max_retries,
                'llm_reasoning': result_json,  # ← Evidencia de que Gemini razonó
                'llm_called': True,  # ← Flag: LLM fue usado
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse LLM response as JSON: {e}")
            logger.error(f"   Response was: {response.text}")
            # Fallback a heurística si parse falla
            return self._fallback_decide_retry(error_code, attempt, max_retries, strategy)
        
        except Exception as e:
            logger.error(f"❌ LLM reasoning failed: {e}")
            import traceback
            traceback.print_exc()
            # Fallback a heurística si Gemini falla
            return self._fallback_decide_retry(error_code, attempt, max_retries, strategy)
    
    def _fallback_decide_retry(self, error_code, attempt, max_retries, strategy):
        """Fallback heurística si LLM falla."""
        
        logger.warning(f"⚠️  Using fallback heuristic (LLM failed)")
        
        if attempt >= max_retries:
            decision = 'fail'
            reason = 'Max retries reached'
        elif strategy['action'] == 'retry':
            decision = 'retry'
            reason = 'Playbook recommends retry'
        else:
            decision = 'fail'
            reason = 'Playbook recommends failure'
        
        return {
            'action': decision,
            'reason': reason,
            'attempt': attempt,
            'max_retries': max_retries,
            'llm_called': False,  # ← Nota: LLM NO fue usado (fallback)
            'fallback': True,  # ← Flag: usamos fallback
        }
    
    async def _tool_apply_backoff(
        self,
        seconds: float,
        toolcontext: Optional[ToolContext] = None
    ) -> Dict[str, Any]:
        """Tool: Apply exponential backoff before retry."""
        
        logger.debug(f"   → Tool: applying backoff ({seconds}s)")
        
        await asyncio.sleep(seconds)
        
        return {
            'status': 'ok',
            'backoff_applied': seconds,
            'timestamp': datetime.now().isoformat(),
        }
    
    # ========================================================================
    # METRICS
    # ========================================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """Return metrics from test execution."""
        
        total_tests = len(self.test_results)
        passed = sum(1 for r in self.test_results if r.get('ok', False))
        failed = total_tests - passed
        llm_used = sum(1 for r in self.test_results if r.get('llm_used', False))
        total_attempts = sum(r.get('attempts', 1) for r in self.test_results)
        avg_attempts = total_attempts / total_tests if total_tests > 0 else 0
        
        return {
            'total_tests': total_tests,
            'passed': passed,
            'failed': failed,
            'success_rate': passed / total_tests if total_tests > 0 else 0,
            'total_attempts': total_attempts,
            'avg_attempts_per_test': avg_attempts,
            'llm_calls': self.llm_calls,
            'tool_calls': self.tool_calls,
            'tests_with_llm_reasoning': llm_used,  # ← MÉTRICA NUEVA
            'llm_participation_rate': llm_used / total_tests if total_tests > 0 else 0,  # ← MÉTRICA NUEVA
        }
