import pytest
from unittest.mock import AsyncMock, patch
from google.adk.evaluation.agent_evaluator import AgentEvaluator
from dotenv import load_dotenv

load_dotenv()


@pytest.mark.asyncio
@patch("src.chaos_engine.agents.order_agent.OrderAgentToolKit.get_playbook", new_callable=AsyncMock)
@patch("src.chaos_engine.agents.order_agent.OrderAgentToolKit.update_pet_status", new_callable=AsyncMock)
@patch("src.chaos_engine.agents.order_agent.OrderAgentToolKit.place_order", new_callable=AsyncMock)
@patch("src.chaos_engine.agents.order_agent.OrderAgentToolKit.find_pets_by_status", new_callable=AsyncMock)
@patch("src.chaos_engine.agents.order_agent.OrderAgentToolKit.get_inventory", new_callable=AsyncMock)
async def test_agent_evaluation(
    mock_get_inventory,
    mock_find_pets,
    mock_place_order,
    mock_update_pet_status,
    mock_get_playbook,
):
    """
    Mock toolkit methods directly → clean 100% success path
    """

    # --- success mocks ---
    mock_get_inventory.return_value = {
        "status": "success",
        "code": 200,
        "data": {"pets": [{"id": 1, "name": "Fluffy", "status": "available"}]},
    }

    mock_find_pets.return_value = {
        "status": "success",
        "code": 200,
        "data": [{"id": 1, "name": "Fluffy", "status": "available"}],
    }

    mock_place_order.return_value = {
        "status": "success",
        "code": 200,
        "data": {"id": "abc123", "status": "placed"},
    }

    mock_update_pet_status.return_value = {
        "status": "success",
        "code": 200,
        "data": {"id": 1, "status": "sold"},
    }

    mock_get_playbook.return_value = {
        "strategy": "retry"
    }

    # --- run evaluation ---
    result = await AgentEvaluator.evaluate(
        agent_module="src.chaos_engine.agents.order_agent",
        eval_dataset_file_path_or_dir="tests/integration/test_cases.json",
    )
