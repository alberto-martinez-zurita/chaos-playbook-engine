# src/chaos_playbook_engine/agents/test_agent.py

from typing import Any, Dict, List

class TestAgent:
    """
    Agent-agnostic experiment runner:
      - Carga una suite de tests (unitarios/flows) y los ejecuta usando un agente ADK/ChaosAgent universal.
      - Guarda métricas de éxito, error, latencia, retries, etc.
      - No conoce lógica de dominio ni playbook, solo ejecuta lo que define la suite.
    """

    def __init__(self, chaos_agent, playbook=None):
        """
        Args:
            chaos_agent: Instancia de ChaosAgent universal o agent ADK compatible.
            playbook: Dict opcional con lógica de retries personalizada (si agent la soporta).
        """
        self.chaos_agent = chaos_agent
        self.playbook = playbook

    async def run_tests(
        self,
        test_suite: Dict[str, Any],
        failure_rate: float = 0.3,
        seed_offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Ejecuta todos los tests de la suite sobre el chaos_agent.

        Args:
            test_suite: dict cargado desde JSON (structure: { "tests": [...] })
            failure_rate: proporción de caos a inyectar
            seed_offset: offset inicial para reproducibilidad

        Returns:
            List[dict]: resultados de cada test con status/chaos/OK y metadata
        """
        results = []
        for idx, test in enumerate(test_suite["tests"]):
            op = test["operation"]
            params = test["params"]
            test_id = test.get("test_id", f"test_{idx+1:04d}")

            try:
                # Puede ajustar aquí para agentes ADK complejos si hace falta
                result = await self.chaos_agent.call(
                    tool_name=op,
                    params=params,
                    failure_rate=failure_rate,
                    seed=seed_offset + idx
                )
                ok = (result["status_code"] == 200) == test.get("expected_success", True)
            except Exception as e:
                result = {"status_code": None, "error": str(e)}
                ok = False

            results.append({
                "test_id": test_id,
                "operation": op,
                "params": params,
                "expected_success": test.get("expected_success", True),
                "status_code": result.get("status_code"),
                "ok": ok,
                "chaos_injected": result.get("chaos_injected", False),
                "error": result.get("error")
            })

        return results
