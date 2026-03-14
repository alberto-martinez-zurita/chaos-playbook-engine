from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.genai import types

from chaos_engine.core.config import load_config, get_model_name
from chaos_engine.tools import petstore_tools, playbook_tools

class OrderAgentToolKit:
    """A class to encapsulate the tools and their dependencies for the OrderAgent."""
    def __init__(self, chaos_proxy, playbook_storage):
        self.chaos_proxy = chaos_proxy
        self.playbook_storage = playbook_storage

    async def get_inventory(self) -> dict:
        return await petstore_tools.get_inventory(self.chaos_proxy)

    async def find_pets_by_status(self, status: str = "available") -> dict:
       raw = await petstore_tools.find_pets_by_status(self.chaos_proxy, status)

       if raw["status"] == "success" and raw.get("data"):
        pet = raw["data"][0]
        return {
            "status": "success",
            "selected_pet_id": pet["id"],
            "selected_pet_name": pet["name"]
        }

        return raw

    async def place_order(self, pet_id: int, quantity: int) -> dict:
        return await petstore_tools.place_order(self.chaos_proxy, pet_id, quantity)

    async def update_pet_status(self, pet_id: int, name: str, status: str) -> dict:
        return await petstore_tools.update_pet_status(self.chaos_proxy, pet_id, name, status)

    async def get_playbook(self) -> dict:
        return await  playbook_tools.get_playbook(self.playbook_storage)
    
    async def wait_seconds(self,seconds: float) -> dict:
        return petstore_tools.wait_seconds(self.chaos_proxy,seconds)

def create_order_agent(model, chaos_proxy, playbook_storage) -> LlmAgent:
    """
    Factory function to create the OrderAgent.

    Args:
        model: The LLM model instance to use.
        chaos_proxy: The proxy for simulating API failures.
        playbook_storage: The storage handler for reading/writing playbook entries.

    Returns:
        An initialized LlmAgent instance for the OrderAgent.
    """
    toolkit = OrderAgentToolKit(chaos_proxy, playbook_storage)

    tools = [
        toolkit.get_inventory,
        toolkit.find_pets_by_status,
        toolkit.place_order,
        toolkit.update_pet_status,
        toolkit.wait_seconds,   
        toolkit.get_playbook
    ]

    return LlmAgent(
        name="OrderAgent",
        model=model,
        instruction="""
           You are the ORDER AGENT.

Your mission is to complete the pet purchase process reliably.

PURCHASE FLOW (STRICT ORDER):

1. get_inventory
2. find_pets_by_status (status="available")
3. place_order
4. update_pet_status

Rules:

- Always follow the steps in exact order.
- Call each tool exactly once unless it fails.
- If a tool fails, immediately call get_playbook and execute the returned strategy.
- Never invent pet IDs or names.
- Always use the exact selected_pet_id and selected_pet_name returned by find_pets_by_status.
- Stop immediately after update_pet_status succeeds.

After completion, output:

[FINAL_STATE]
{
  "selected_pet_id": <id>,
  "completed": true,
  "error": null
}
        """,
        output_key="steps_performed",
        tools=tools
    )

# The ADK's AgentEvaluator expects to find a top-level variable named `agent`.
# We create a default instance here. The evaluator will handle dependency
# injection for the arguments during the evaluation process.

# 1. Load Configuration
config = load_config()
model_name = get_model_name(config)