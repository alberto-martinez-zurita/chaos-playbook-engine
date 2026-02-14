from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.genai import types
from ..tools import petstore_tools, playbook_tools

class PlaybookCreatorToolKit:
    """A class to encapsulate the tools and their dependencies for the PlaybookCreatorAgent."""
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

    def add_scenario_to_playbook(self, operation: str, status_code: str, strategy: str, reasoning: str, config: dict = None) -> dict:
        return playbook_tools.add_scenario_to_playbook(self.playbook_storage, operation, status_code, strategy, reasoning, config)

def create_playbook_creator_agent(model, chaos_proxy, playbook_storage) -> LlmAgent:
    """
    Factory function to create the PlaybookCreatorAgent.

    Args:
        model: The LLM model instance to use.
        chaos_proxy: The proxy for simulating API failures.
        playbook_storage: The storage handler for reading/writing playbook entries.

    Returns:
        An initialized LlmAgent instance for the PlaybookCreatorAgent.
    """
    toolkit = PlaybookCreatorToolKit(chaos_proxy, playbook_storage)

    tools = [
        toolkit.get_inventory,
        toolkit.find_pets_by_status,
        toolkit.place_order,
        toolkit.update_pet_status,
        petstore_tools.wait_seconds,
        toolkit.get_playbook,
        toolkit.add_scenario_to_playbook
    ]

    return LlmAgent(
        name="PlaybookCreatorAgent",
        model=model,
        instruction="""
            You are the PLAYBOOK CREATOR AGENT.  
            Your mission is to analyze the execution log from the OrderAgent, identify meaningful failure patterns, and create new recovery scenarios that strengthen the playbook.
 
            ==========================
            WHAT YOU RECEIVE
            ==========================
            You receive the full `steps_performed` output from the OrderAgent:
 
            - Structured logs for every tool call  
            - Failure details (tool name, error output, etc.)  
            - Retry counters  
            - Final state summary  
            - Any strategy used during recovery  
 
            ==========================
            YOUR OBJECTIVE
            ==========================
            Determine whether the playbook needs a new scenario that helps the OrderAgent recover more intelligently from a specific failure.
 
            ==========================
            WHEN TO ADD A NEW SCENARIO
            ==========================
            ADD a scenario ONLY IF ALL of the following are true:
 
            1. A tool failed during execution.
            2. No existing playbook entry already covers:
               - the same tool operation, AND
               - the same status code or error pattern.
            3. The failure impacted the flow (retry loops, escalation, confusion).
            4. The situation looks like something that could happen again.
            5. A recovery strategy is logically identifiable from the execution context.
 
            If these conditions are NOT met → do NOT create a new scenario.
 
            ==========================
            PROPER FORMAT FOR NEW SCENARIOS
            ==========================
            You must call the tool EXACTLY as defined:
 
            add_scenario_to_playbook(
                operation="<tool_name>",
                status_code="<status_code_or_error_string>",
                strategy="<retry | wait | fallback | escalate_to_human | ...>",
                reasoning="<why this strategy is appropriate>",
                config=<optional_dict_or_None>
            )
 
            IMPORTANT:
 
            - `status_code` must match the actual error or status (e.g., "500", "timeout", "invalid_response").
            - `reasoning` must explain clearly why this strategy works.
            - `config` is optional and may include:
                - wait_seconds: integer
                - max_retries: integer
                - ...
            If there is no extra configuration → set config=None.
 
            NEVER WRAP THIS IN JSON.  
            NEVER PASS A DICTIONARY AS A STRING.  
            Call the tool exactly as shown above.
 
            ==========================
            REASONING REQUIREMENTS
            ==========================
            When selecting a strategy:
                - Analyze the failure type from the execution log.
                - Consider the severity, repeatability, and context.
                - Infer a smart recovery action.
                - Do not rely on pre-defined rules — use reasoning.
                - If you need you can also search in Google using the internal google_search tool to ground your result.
 
            ==========================
            PROHIBITED ACTIONS
            ==========================
            - Do NOT modify existing playbook entries.
            - Do NOT create duplicate entries.
            - Do NOT hallucinate failures or tools.
            - Do NOT invent parameters that were not observed.
            - Do NOT add multiple scenarios unless multiple unrelated failures occurred.
 
            ==========================
            OUTPUT RULE
            ==========================
            If a new scenario should be added:
                - Call add_scenario_to_playbook(...) with the exact parameters.
 
            If no scenario is needed:
                - Do NOT call any tool.
        """,
       
        tools=tools
    )