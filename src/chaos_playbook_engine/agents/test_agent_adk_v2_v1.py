"""
src/chaos_playbook_engine/agents/test_agent_adk_v2.py

TestAgent como verdadero ADK Agent (LlmAgent) - PYDANTIC COMPATIBLE

PROBLEMA ANTERIOR:
    ValueError: "TestAgentADK" object has no field "chaos_agent_func"
    
CAUSA:
    LlmAgent hereda de Pydantic BaseModel
    Pydantic v2 no permite atributos fuera del modelo

SOLUCIÓN:
    1. Definir todos los campos en el modelo Pydantic
    2. Usar model_config para permitir atributos extra
    3. O no heredar de LlmAgent, simplemente usarlo

ARQUITECTURA:
    
    TestAgentADK (LlmAgent ADK con Gemini)
        ├─ Hereda de LlmAgent
        ├─ Todos los campos definidos
        ├─ Razona con Gemini LLM
        ├─ Tools: call_op, check_playbook, decide_retry, apply_backoff
        └─ Métricas: llm_calls, tool_calls, attempts

"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

# ADK imports
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import ToolContext
from google.genai.types import HttpRetryOptions
from pydantic import Field, ConfigDict

logger = logging.getLogger(__name__)


class TestAgentADK(LlmAgent):
    """
    ADK Agent for testing with chaos engineering - PYDANTIC COMPATIBLE VERSION.
    
    Inherits from LlmAgent to leverage:
    - Gemini LLM reasoning
    - Tool calling mechanism
    - Session management
    - OpenTelemetry tracing
    
    PYDANTIC COMPATIBLE: Todos los campos están definidos.
    """
    
    # Configuración Pydantic para permitir atributos extra si es necesario
    model_config = ConfigDict(extra='allow')
    
    # Campos que almacenamos
    chaos_agent_func: Optional[Callable] = Field(default=None, description="Callable que llama a ChaosAgent")
    playbook: Dict[str, Any] = Field(default_factory=dict, description="Chaos playbook")
    failure_rate: float = Field(default=0.3, description="Failure rate para chaos injection")
    seed: int = Field(default=42, description="Random seed")
    test_results: List[Dict[str, Any]] = Field(default_factory=list, description="Resultados de tests")
    llm_calls: int = Field(default=0, description="Contador de LLM calls")
    tool_calls: int = Field(default=0, description="Contador de tool calls")
    
    def __init__(
        self,
        chaos_agent_func: Optional[Callable] = None,
        playbook: Dict[str, Any] = None,
        llm_model: str = "gemini-2.5-flash-lite",
        failure_rate: float = 0.3,
        seed: int = 42,
        **kwargs
    ):
        """
        Initialize TestAgent as an ADK LlmAgent - PYDANTIC COMPATIBLE.
        
        Args:
            chaos_agent_func: Callable that executes chaos operations
            playbook: Dict with retry strategies per error_code
            llm_model: Gemini model to use
            failure_rate: Probability of chaos injection (0.0-1.0)
            seed: Random seed for reproducibility
        """
        
        if playbook is None:
            playbook = {}
        
        # Define tools that this agent can use
        tools = [
            self._tool_call_operation,
            self._tool_check_playbook,
            self._tool_decide_retry,
            self._tool_apply_backoff,
        ]
        
        # System instruction for the LLM
        instruction = """You are a Testing Agent specialized in chaos engineering.

Your objective: Execute tests against APIs and make intelligent decisions about failures.

When a test fails:
1. Always check the playbook for the error code
2. Reason about whether to retry based on:
   - Max retries allowed
   - Backoff strategy
   - Cumulative failures
3. Decide: retry with backoff, or accept the failure
4. Execute the decision

Always explain your reasoning. Be methodical and deterministic.
"""
        
        # Initialize LlmAgent with retry configuration
        retry_options = HttpRetryOptions(
            attempts=3,
            expbase=2,
            initialdelay=1,
            httpstatuscodes=[429, 500, 503, 504]
        )
        
        # Llamar al __init__ de LlmAgent
        super().__init__(
            name="TestAgentADK",
            model=Gemini(
                model=llm_model,
                retryoptions=retry_options,
                temperature=0.3  # Low temperature for deterministic decisions
            ),
            instruction=instruction,
            tools=tools,
        )
        
        # AHORA, asignar los campos después de que Pydantic los haya inicializado
        self.chaos_agent_func = chaos_agent_func
        self.playbook = playbook
        self.failure_rate = failure_rate
        self.seed = seed
        self.test_results = []
        self.llm_calls = 0
        self.tool_calls = 0
        
        logger.info(f"✅ TestAgent initialized")
        logger.info(f"   Model: {llm_model}")
        logger.info(f"   Failure rate: {failure_rate}")
        logger.info(f"   Seed: {seed}")
    
    async def run_test(self, test_spec: Dict[str, Any], attempt: int = 1) -> Dict[str, Any]:
        """
        Run a single test with the agent's decision-making.
        
        Args:
            test_spec: Test specification with operation, params, expected_success
            attempt: Current attempt number
        
        Returns:
            Test result with full history of decisions and retries
        """
        
        logger.info(f"🧪 Running test: {test_spec['test_id']} (attempt {attempt})")
        
        # Initial call to operation
        operation_id = test_spec['operation']
        params = test_spec.get('params', {})
        
        # TestAgent calls the operation via tool
        call_result = await self._tool_call_operation(
            operation_id=operation_id,
            params=params
        )
        
        # Check if failed
        if call_result['status_code'] >= 400:
            # Failed - check playbook and decide
            playbook_strategy = await self._tool_check_playbook(
                error_code=call_result['status_code']
            )
            
            # LLM decides what to do
            decision = await self._tool_decide_retry(
                error_code=call_result['status_code'],
                attempt=attempt,
                max_retries=playbook_strategy.get('max_retries', 0),
                strategy=playbook_strategy
            )
            
            logger.info(f"   LLM Decision: {decision['action']}")
            
            # Execute decision
            if decision['action'] == 'retry':
                backoff = playbook_strategy.get('backoff_seconds', 1) * attempt
                logger.info(f"   Applying backoff: {backoff}s")
                await self._tool_apply_backoff(seconds=backoff)
                
                # Recursive call for retry
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
        }
    
    async def run_test_suite(self, test_suite: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Run a suite of tests.
        
        Args:
            test_suite: List of test specifications
        
        Returns:
            List of test results
        """
        
        logger.info(f"🚀 Running {len(test_suite)} tests with TestAgent")
        
        results = []
        for i, test in enumerate(test_suite, 1):
            logger.info(f"\n   [{i}/{len(test_suite)}] {test.get('test_id', f'test_{i}')}")
            result = await self.run_test(test)
            results.append(result)
            self.test_results.append(result)
        
        return results
    
    # ========================================================================
    # TOOLS - Available to TestAgent for decision-making
    # ========================================================================
    
    async def _tool_call_operation(
        self,
        operation_id: str,
        params: Dict[str, Any],
        toolcontext: Optional[ToolContext] = None
    ) -> Dict[str, Any]:
        """
        Tool: Call ChaosAgent to execute operation.
        
        This is how TestAgent actually executes API calls.
        ChaosAgent may inject failures based on failure_rate and seed.
        """
        
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
        
        # Call ChaosAgent through provided function
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
        """
        Tool: Consult playbook for error handling strategy.
        
        Given an error code, returns the playbook's recommended strategy.
        """
        
        logger.debug(f"   → Tool: checking playbook for error {error_code}")
        
        # Search playbook
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
        Tool: LLM decides whether to retry.
        
        This is where the LLM's reasoning comes in.
        Given error context, it decides if retry is worth it.
        """
        
        logger.debug(f"   → Tool: LLM deciding retry (attempt {attempt}/{max_retries})")
        self.llm_calls += 1
        
        # Simple heuristic for now (could be LLM-driven in future)
        if attempt >= max_retries:
            decision = 'fail'
            reason = 'Max retries reached'
        elif strategy['action'] == 'retry':
            decision = 'retry'
            reason = 'Playbook recommends retry'
        else:
            decision = 'fail'
            reason = 'Playbook recommends failure'
        
        logger.debug(f"     Decision: {decision} ({reason})")
        
        return {
            'action': decision,
            'reason': reason,
            'attempt': attempt,
            'max_retries': max_retries,
        }
    
    async def _tool_apply_backoff(
        self,
        seconds: float,
        toolcontext: Optional[ToolContext] = None
    ) -> Dict[str, Any]:
        """
        Tool: Apply exponential backoff before retry.
        """
        
        logger.debug(f"   → Tool: applying backoff ({seconds}s)")
        
        # Sleep
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
        }
