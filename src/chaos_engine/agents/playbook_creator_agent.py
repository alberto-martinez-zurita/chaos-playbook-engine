from typing import TypedDict, Optional, List
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from ..tools import petstore_tools
from ..core.playbook_storage import PlaybookStorage

# TypedDict for optional scenario config
class ScenarioConfig(TypedDict, total=False):
    wait_seconds: int
    max_retries: int

# TypedDict for add_scenario_to_playbook response
class AddScenarioResponse(TypedDict):
    message: str

class PlaybookCreatorToolKit:
    """Encapsulates all tools for the PlaybookCreatorAgent."""

    def __init__(self, chaos_proxy, playbook_storage: PlaybookStorage):
        self.chaos_proxy = chaos_proxy
        self.playbook_storage = playbook_storage

    # Petstore tools
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

    # Playbook tools
    async def get_playbook(self) -> List[dict]:
        return await self.playbook_storage.load_procedures()

    async def add_scenario_to_playbook(
        self,
        failure_type: str,
        api: str,
        recovery_strategy: str,
        wait_seconds: int = 0,
        max_retries: int = 1
    ) -> dict:
        """
        Adds a new recovery procedure to the playbook.

        Returns a dict with a message (Gemini-safe).
        """
        metadata = {
            "wait_seconds": wait_seconds,
            "max_retries": max_retries
        }

        procedure_id = await self.playbook_storage.save_procedure(
            failure_type=failure_type,
            api=api,
            recovery_strategy=recovery_strategy,
            metadata=metadata
        )

        return {"message": f"Successfully added new procedure with ID: {procedure_id}"}


def create_playbook_creator_agent(model, chaos_proxy, playbook_storage: PlaybookStorage) -> LlmAgent:
    """
    Creates a Gemini-safe LlmAgent for the PlaybookCreatorAgent.
    """
    toolkit = PlaybookCreatorToolKit(chaos_proxy, playbook_storage)

    tools = [
        toolkit.get_inventory,
        toolkit.find_pets_by_status,
        toolkit.place_order,
        toolkit.update_pet_status,
        toolkit.wait_seconds,
        toolkit.get_playbook,
        toolkit.add_scenario_to_playbook
    ]

    return LlmAgent(
        name="PlaybookCreatorAgent",
        model=model,
        instruction="""
        You are the PLAYBOOK CREATOR AGENT.
        Your mission is to analyze the execution log from the OrderAgent
        and create new recovery scenarios if necessary.
        Follow the rules for when to add a scenario, and call add_scenario_to_playbook exactly as defined.
        """,
        tools=tools
    )
