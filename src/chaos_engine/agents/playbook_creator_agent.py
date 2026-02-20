from typing import TypedDict, List, Dict, Any
from google.adk.agents import LlmAgent
from ..tools import petstore_tools
from ..tools.playbook_tools import get_playbook, add_scenario_to_playbook
from ..core.playbook_storage import PlaybookStorage


class AddScenarioResponse(TypedDict):
    message: str


class PlaybookCreatorToolKit:
    """Encapsulates all tools for the PlaybookCreatorAgent."""

    def __init__(self, chaos_proxy, playbook_storage: PlaybookStorage):
        self.chaos_proxy = chaos_proxy
        self.playbook_storage = playbook_storage

    # =========================
    # Petstore tools
    # =========================
    async def get_inventory(self) -> List[dict]:
        return await petstore_tools.get_inventory(self.chaos_proxy)

    async def find_pets_by_status(self, status: str = "available") -> List[dict]:
        return await petstore_tools.find_pets_by_status(self.chaos_proxy, status)

    async def place_order(self, pet_id: int, quantity: int) -> dict:
        return await petstore_tools.place_order(self.chaos_proxy, pet_id, quantity)

    async def update_pet_status(self, pet_id: int, name: str, status: str) -> dict:
        return await petstore_tools.update_pet_status(self.chaos_proxy, pet_id, name, status)

    async def wait_seconds(self, seconds: int) -> str:
        return await petstore_tools.wait_seconds(seconds)

    # =========================
    # Playbook tools
    # =========================
    async def get_playbook_tool(self) -> Dict[str, Any]:
        """Returns the full playbook via the tool function."""
        return await get_playbook(self.playbook_storage)

    async def add_scenario_to_playbook_tool(
        self,
        api: str,
        status_code: int,
        strategy: str,
        reasoning: str,
        config: dict  # <- plain dict, no extra schema hints
    ) -> dict:
        """
        Adds a new scenario using the playbook tool.
        Returns a confirmation dict.
        """
        scenario_payload = {
            "strategy": strategy,
            "reasoning": reasoning,
            "config": config
        }

        # Call the actual playbook function
        return await add_scenario_to_playbook(
            storage=self.playbook_storage,
            api=api,
            status_code=status_code,
            strategy_payload=scenario_payload
    )


def create_playbook_creator_agent(model, chaos_proxy, playbook_storage: PlaybookStorage) -> LlmAgent:
    toolkit = PlaybookCreatorToolKit(chaos_proxy, playbook_storage)

    tools = [
        toolkit.get_inventory,
        toolkit.find_pets_by_status,
        toolkit.place_order,
        toolkit.update_pet_status,
        toolkit.wait_seconds,
        toolkit.get_playbook_tool,
        toolkit.add_scenario_to_playbook_tool
    ]

    return LlmAgent(
        name="PlaybookCreatorAgent",
        model=model,
        instruction="""
        You are the PLAYBOOK CREATOR AGENT.

Your mission is to analyze an API execution log, detect any error conditions, and create a structured recovery playbook in the exact JSON format described below.

RULES:

1. The output must be **a single valid JSON object**.
2. The JSON keys are **API names** (e.g., "get_inventory", "find_pets_by_status", "place_order", "update_pet_status").
3. For each API, the keys are **HTTP status codes or internal error codes** (as strings), e.g., "400", "401", "408", "500".
4. For each status code, the value is an object with:
   - `"strategy"`: the recovery strategy (one of `fail_fast`, `retry_linear_backoff`, `retry_exponential_backoff`, `wait_and_retry`, `escalate_to_human`).
   - `"reasoning"`: a concise, human-readable explanation for the strategy. Can be omitted if not needed (except for `escalate_to_human`, which must have reasoning).
   - `"config"`: a dictionary containing any parameters needed for the strategy (e.g., `delay`, `wait_seconds`, `base_delay`, `max_retries`). Leave empty `{}` if not applicable.

5. If you are unsure of the status code or API behavior, use `"default": { "strategy": "escalate_to_human", "reasoning": "Unknown error scenario.", "config": {} }`.

6. The JSON must **match this structure exactly**, including all required fields.

Example output for one API:

{
  "get_inventory": {
    "400": {
      "strategy": "fail_fast",
      "reasoning": "Bad Request on GET. Logic error.",
      "config": {}
    },
    "408": {
      "strategy": "retry_linear_backoff",
      "reasoning": "Read timeout. Safe to retry.",
      "config": { "delay": 1.0, "max_retries": 3 }
    }
  }
}

Use this structure for all APIs and relevant status codes.

---

Given a user request or execution log, produce a complete JSON playbook following these rules.
        """
        ,
        tools=tools
    )