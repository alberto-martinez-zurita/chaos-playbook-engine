"""
PetstoreAgent - Real API Chaos Implementation (Phase 6)
======================================================
FINAL VERSION: Dependency Injection (DI) Applied.
Corrige el acoplamiento y el error de sintaxis.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Protocol, Set, Type, runtime_checkable

from dotenv import load_dotenv

# Framework
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner

# Core Logic
from chaos_engine.core.config import load_config, get_model_name
from chaos_engine.core.protocols import Executor


@runtime_checkable
class LLMClientConstructor(Protocol):
    def __call__(self, model: str, temperature: float) -> Gemini: ...


class PetstoreAgent:
    """
    Agente que opera sobre la API real de Petstore v3 a través de un ChaosProxy.
    """

    def __init__(
        self,
        playbook_path: str,
        tool_executor: Executor,
        llm_client_constructor: Type[Gemini],
        model_name: str,
        verbose: bool = False,
        mock_mode: bool = None,
    ):
        # 1. CARGA EXPLÍCITA DE CREDENCIALES Y CONFIG
        load_dotenv() 
        if not os.getenv("GOOGLE_API_KEY"):
             raise ValueError("❌ CRITICAL: GOOGLE_API_KEY not found.")

        # 2. ASIGNACIÓN DE DEPENDENCIAS
        self.executor = tool_executor
        self.llm_client_constructor = llm_client_constructor
        self.model_name = model_name
        self.verbose = verbose
        self.logger = logging.getLogger("PetstoreAgent")
        self.mock_mode = mock_mode 

        # 3. CARGA DE DATOS Y ESTADO
        self.playbook_path = playbook_path
        self.playbook_data = self._load_playbook()
        self.successful_steps: Set[str] = set()

    def _load_playbook(self) -> Dict:
        try:
            with open(self.playbook_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            self.logger.error("Error loading playbook %s", self.playbook_path, exc_info=True)
            return {}

    # ====================================================================
    # ✅ FIX: HERRAMIENTAS COMO MÉTODOS (Pilar I: Mantenibilidad Cognitiva)
    # ====================================================================

    async def get_inventory(self) -> dict:
        """Returns a map of status codes to quantities."""
        res = await self.executor.send_request("GET", "/store/inventory")
        if res.get("status") == "success": self.successful_steps.add("get_inventory")
        return res

    async def find_pets_by_status(self, status: str = "available") -> dict:
        """Finds Pets by status."""
        res = await self.executor.send_request("GET", "/pet/findByStatus", params={"status": status})
        if res.get("status") == "success": self.successful_steps.add("find_pets_by_status")
        return res

    async def place_order(self, pet_id: int, quantity: int) -> dict:
        """Place an order for a pet. REQUIRES valid pet_id from find_pets."""
        body = {"petId": pet_id, "quantity": quantity, "status": "placed", "complete": False}
        res = await self.executor.send_request("POST", "/store/order", json_body=body)
        if res.get("status") == "success": self.successful_steps.add("place_order")
        return res

    async def update_pet_status(self, pet_id: int, name: str, status: str) -> dict:
        """Update pet status. REQUIRES valid pet_id."""
        body = {"id": pet_id, "name": name, "status": status, "photoUrls": []}
        res = await self.executor.send_request("PUT", "/pet", json_body=body)
        if res.get("status") == "success": self.successful_steps.add("update_pet_status")
        return res

    async def wait_seconds(self, seconds: float) -> dict:
        """
        Pauses execution (Backoff strategy).
        Llama al Executor (Proxy) para calcular el tiempo con Jitter.
        """
        
        # ✅ FIX: Llamar al Proxy para calcular Jitter
        # self.executor es el ChaosProxy (o Circuit Breaker), que implementa el método.
        jittered_seconds = self.executor.calculate_jittered_backoff(seconds)
        
        if self.verbose:
            self.logger.info("WAIT STRATEGY: Base %.2fs -> Jittered %.2fs", seconds, jittered_seconds)
        
        # Usar el tiempo aleatorio
        await asyncio.sleep(jittered_seconds) 
        
        # Reportar el tiempo real usado
        return {"status": "success", "message": f"Waited {jittered_seconds:.2f} seconds"}

    async def lookup_playbook(self, tool_name: str, error_code: str) -> Dict[str, Any]:
        """Consults the Chaos Playbook."""
        if self.verbose: self.logger.info("PLAYBOOK LOOKUP: %s -> %s", tool_name, error_code)
        tool_config = self.playbook_data.get(tool_name, {})
        strategy = tool_config.get(str(error_code))
        if strategy:
            return {"status": "success", "found": True, "recommendation": strategy}
        default = self.playbook_data.get("default")
        return {"status": "success", "found": False, "recommendation": default}

    async def report_workflow_failure(self, reason: str = "Unknown failure") -> dict:
        """Call if you cannot proceed."""
        if self.verbose: self.logger.error("FAILURE REPORTED: %s", reason)
        return {"status": "success", "message": "Failure reported"}

    def get_tool_list(self) -> List:
        """Devuelve la lista de tools para el LlmAgent."""
        return [
            self.get_inventory, self.find_pets_by_status, self.place_order, self.update_pet_status, 
            self.lookup_playbook, self.wait_seconds, self.report_workflow_failure
        ]

    # ====================================================================
    # ✅ FIX: process_order (Lógica de Éxito Determinista)
    # ====================================================================

    async def process_order(self, order_id: str, failure_rate: float, seed: int) -> Dict[str, Any]:
        
        self.successful_steps = set() # Reinicio de estado
        
        adk_agent = LlmAgent(
            name="PetstoreChaosAgent",
            model=self.llm_client_constructor(model=self.model_name, temperature=0.0), 
            instruction=f"""
            SYSTEM ROLE: DETERMINISTIC WORKFLOW ENGINE
            You are not a chat assistant. You are a robotic process execution engine.
            Order ID: {order_id}

            ====================
            EXECUTION PROTOCOL (PRIMARY FLOW)
            ====================
            You MUST execute the following 4 tools in STRICT SEQUENCE.
            You MUST use the EXACT parameters defined below. Do not guess.

            1. CALL `get_inventory()`
            - Verify stock levels.

            2. CALL `find_pets_by_status(status='available')`
            - CRITICAL: You MUST explicitly provide `status='available'`.
            - From the result, EXTRACT the first `id` and `name`.

            3. CALL `place_order(pet_id=..., quantity=1)`
            - Use the `id` from Step 2.
            - CRITICAL: You MUST explicitly provide `quantity=1`.

            4. CALL `update_pet_status(pet_id=..., status='sold', name=...)`
            - Use the `id` and `name` from Step 2.
            - CRITICAL: You MUST explicitly provide `status='sold'`.

            ==============================================
             ERROR HANDLING (CONDITIONAL CHAOS RESPONSE)
            ==============================================
            If AND ONLY IF the last API tool call (Steps 1-4) returns an error status:
            1. IMMEDIATELY call `lookup_playbook(tool_name, error_code)`.
            2. OBEY the playbook strategy strictly:
            - If "Retry": Call the failed tool again.
            - If "Wait": Call `wait_seconds(seconds)`.
            - If "Escalate": Call `report_workflow_failure`.

            ====================
            FINAL OUTPUT FORMAT
            ====================
            Upon successful completion of Step 4, you MUST output a Single Raw JSON Object.
            DO NOT use Markdown code blocks (no ```json).
            DO NOT add conversational text.
            Output EXACTLY this structure:

            
            "selected_pet_id": <integer_id>,
            "completed": true,
            "error": null
            
            """,
            tools=self.get_tool_list()
        )

        runner = InMemoryRunner(agent=adk_agent, app_name="chaos_playbook")
        start_time = time.time()
        
        # 🚨 FIX ESTRUCTURAL: El try-except debe envolver el bloque de ejecución, no la definición.
        try:
            # Le damos un empujón inicial claro
            await runner.run_debug(f"Inicia la secuencia obligatoria para {order_id}. Llama a la herramienta 1 (get_inventory).")
            
            duration_ms = (time.time() - start_time) * 1000
            
            # ✅ VALIDACIÓN DE ÉXITO FINAL (Código Python, no LLM)
            REQUIRED_STEPS = {"get_inventory", "find_pets_by_status", "place_order", "update_pet_status"}
            is_complete = REQUIRED_STEPS.issubset(self.successful_steps)
            
            status = "success" if is_complete else "failure"
            
            if self.verbose:
                self.logger.debug("Pasos completados: %d/4 -> %s", len(self.successful_steps), status)
            
            return {
                "status": status,
                "steps_completed": list(self.successful_steps), 
                "failed_at": "unknown" if status == "success" else "incomplete_workflow",
                "duration_ms": duration_ms
            }

        except Exception as e:
            self.logger.exception("Runner exception during process_order")
            return {
                "status": "failure",
                "steps_completed": list(self.successful_steps), 
                "failed_at": "exception",
                "error": str(e),
                "duration_ms": 0.0
            }