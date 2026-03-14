from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.genai import types

from chaos_engine._legacy.agents.order_agent import create_order_agent
from chaos_engine.chaos.proxy import ChaosProxy
from chaos_engine.core.playbook_storage import PlaybookStorage
from chaos_engine.core.config import load_config, get_model_name


 
# The ADK's AgentEvaluator expects to find a top-level variable named `agent`.
# This script create this agent and configure it to use the proxy in mock mode to have a deterministic integration test

# Load Configuration
config = load_config()
model_name = get_model_name(config)

#Create proxy
chaos_proxy= ChaosProxy(
    failure_rate=0.0,
    seed=42,
    mock_mode=True,
    verbose=True
)


#Load Playbook
playbook_storage=PlaybookStorage("../../data/playbook_training.json")

agent = create_order_agent(
    model=Gemini( model=model_name,
        retry_options=types.HttpRetryOptions(
            attempts=5,
            exp_base=7,
            initial_delay=1,
            http_status_codes=[429, 500, 503, 504],
    )),
    chaos_proxy=chaos_proxy,  
    playbook_storage=playbook_storage,   
)