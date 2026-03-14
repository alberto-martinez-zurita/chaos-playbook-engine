from __future__ import annotations

from google.adk.agents import LlmAgent, LoopAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
import sys
from pathlib import Path
import argparse
import asyncio
from google.genai import types
from dotenv import load_dotenv
from functools import partial, update_wrapper

# Ensure the src directory is in the Python path
project_root = Path(__file__).resolve().parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from chaos_engine.chaos.proxy import ChaosProxy
from chaos_engine.core.playbook_storage import PlaybookStorage
from chaos_engine.tools import playbook_tools, petstore_tools
from chaos_engine.agents.order_agent import create_order_agent
from chaos_engine.agents.playbook_creator_agent import create_playbook_creator_agent
from chaos_engine.core.config import load_config, get_model_name

load_dotenv() 

async def train_agent(args):
    # 1. Setup Dependencies
    print(f"🔧 Initializing training with Failure Rate: {args.failure_rate}, Seed: {args.seed}")
    config = load_config()
    model_name = get_model_name(config)
    chaos_proxy = ChaosProxy(failure_rate=args.failure_rate, mock_mode=args.mock_mode, seed=args.seed)
    playbook_storage = PlaybookStorage(args.playbook_path)
    model = Gemini(
        model=model_name,
        retry_options=types.HttpRetryOptions(
            attempts=5,
            exp_base=7,
            initial_delay=1,
            http_status_codes=[429, 500, 503, 504],
        )
    )

    # 2. Create Agents using Factories
    # The factories now handle tool creation and dependency injection internally.
    orderAgent = create_order_agent(model, chaos_proxy, playbook_storage)
    playbookCreatorAgent = create_playbook_creator_agent(model, chaos_proxy, playbook_storage)

    # 3. Define the Training Loop
    trainingAgent = LoopAgent(
        name="TrainingLoop",
        sub_agents=[orderAgent, playbookCreatorAgent],
        max_iterations=args.max_iterations,
    )

    # 4. Run the training
    print(f"🚀 Starting training loop for {args.max_iterations} iterations...")
    runner = InMemoryRunner(agent=trainingAgent)
    await runner.run_debug("Purchase an available pet.")
    print("\n✅ Training complete.")
    print(f"📘 Playbook updated at: {args.playbook_path}")
 
def parse_args():
    """Parses command-line arguments for the training script."""
    parser = argparse.ArgumentParser(description="Run the training loop for the Chaos Playbook Engine.")
    parser.add_argument("--failure-rate", type=float, default=0.6, help="The probability of failure for API calls.")
    parser.add_argument("--max-iterations", type=int, default=5, help="The number of training loops to run.")
    parser.add_argument("--playbook-path", type=str, default="data/playbook_training.json", help="Path to the playbook JSON file.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument("--mock-mode", action="store_true", help="Run the training in mock mode. Defaults to False.")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(train_agent(args))
 
 