import pytest
from unittest.mock import AsyncMock, patch
from google.adk.evaluation.agent_evaluator import AgentEvaluator
from dotenv import load_dotenv

load_dotenv()


@pytest.mark.asyncio
async def test_agent_evaluation():
    # --- run evaluation ---
    result = await AgentEvaluator.evaluate(
        agent_module="src.chaos_engine.agents.order_agent_evaluator",
        eval_dataset_file_path_or_dir="tests/integration/test_cases.json",
    )
