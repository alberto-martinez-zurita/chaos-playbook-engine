from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.genai import types
from ..tools import petstore_tools, playbook_tools

class OrderAgentToolKit:
    """A class to encapsulate the tools and their dependencies for the OrderAgent."""
    def __init__(self, chaos_proxy, playbook_storage):
        self.chaos_proxy = chaos_proxy
        self.playbook_storage = playbook_storage

    async def get_inventory(self) -> dict:
        return await petstore_tools.get_inventory(self.chaos_proxy)

    async def find_pets_by_status(self, status: str = "available") -> dict:
        return await petstore_tools.find_pets_by_status(self.chaos_proxy, status)

    async def place_order(self, pet_id: int, quantity: int) -> dict:
        return await petstore_tools.place_order(self.chaos_proxy, pet_id, quantity)

    async def update_pet_status(self, pet_id: int, name: str, status: str) -> dict:
        return await petstore_tools.update_pet_status(self.chaos_proxy, pet_id, name, status)

    async def get_playbook(self) -> dict:
        return playbook_tools.get_playbook(self.playbook_storage)

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
        petstore_tools.wait_seconds,  # This tool has no dependencies
        toolkit.get_playbook
    ]

    return LlmAgent(
        name="OrderAgent",
        model=model,
        instruction="""
            You are the ORDER AGENT.  
            Your mission is to complete the pet purchase process reliably, even under failures and API instability.
    
            ==========================
            PRIMARY OBJECTIVE
            ==========================
            Complete the PURCHASE FLOW:
    
            1. Check the inventory → (get_inventory)
            2. Look for an available pet → (find_pets_by_status)
               - Must select ONE valid pet ID from the results.
            3. Purchase that pet → (place_order)
            4. Mark the pet as sold → (update_pet_status)
    
            If all four steps succeed, the purchase is complete.
    
            ==========================
            MANDATORY REPORTING FORMAT
            ==========================
            For EVERY tool call you make, you MUST produce a structured log entry in this format:
    
            [STEP <n>]
            TOOL: <tool_name>
            PARAMS: <json>
            RESULT: <raw tool output | raw error>
            STRATEGY_DECISION: <what you decided and why>
    
            At the end, produce a final section:
    
            [FINAL_STATE]
            {
            "selected_pet_id": <id or null>,
            "retry_counters": { "<tool>": <number> },
            "last_error": <string or null>,
            "completed": true|false
            }
    
            ==========================
            STATE REQUIREMENTS
            ==========================
            You MUST track:
    
            - selected_pet_id
            - retry counters per tool
            - last_error
            - last_playbook_strategy
    
            Include these in the final output (steps_performed).
    
            ==========================
            FAILURE PROTOCOL (CRITICAL)
            ==========================
            If a tool call fails in ANY way (HTTP error, timeout, malformed response, null data):
    
            1. IMMEDIATELY call get_playbook
            2. When the playbook responds with a strategy:
                - DO NOT ask the user.
                - EXECUTE THE STRATEGY IMMEDIATELY.
    
    
            ==========================
            GENERAL RULES
            ==========================
            - Always follow the purchase flow strictly in order.
            - Never select a pet ID that does not appear in the results.
            - Never skip a failing step unless the playbook explicitly instructs it.
            - Never hallucinate successful results.
            - Your success metric is FINISHING THE PURCHASE UNASSISTED despite failures.
            - In case the strategy suggested is escalate_to_human, you have to stop the execution and return a message to let the human complete or correct the order procedure
        """,
        output_key="steps_performed",
        tools=tools
    )