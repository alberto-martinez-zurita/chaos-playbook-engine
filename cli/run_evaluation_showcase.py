"""
run_evaluation_showcase.py
==========================
Observability Capabilities Demonstration Script (Google ADK).

This script does not run a massive chaos experiment.
Its purpose is to demonstrate how the framework can:
1. Evaluar la calidad de la respuesta del agente.
1. Evaluate the quality of the agent's response.
2. Validate the tool usage trajectory.
3. Generate detailed reports in table format.

Usage:
    poetry run python cli/run_evaluation_showcase.py
"""
from __future__ import annotations

import sys
import asyncio
import json
import tempfile
import os
import logging
from pathlib import Path
from unittest.mock import patch

# Añadir src al path
src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Importaciones del Framework
from google.adk.evaluation.agent_evaluator import AgentEvaluator
from chaos_engine.core.config import load_config
from chaos_engine.core.logging import setup_logger

# Ensure the agent module is loaded for patching
import chaos_engine.agents.order_agent

async def run_showcase():
    # 1. Basic Configuration
    logger = setup_logger("adk_showcase", verbose=True)
    logger.info("="*80)
    logger.info("🚀 GOOGLE ADK OBSERVABILITY SHOWCASE")
    logger.info("="*80)
    
    # 2. Define the "Golden Dataset" (The ideal test case)
    # We create it temporarily for the ADK to read
    golden_case = [
        {
            "id": "SHOWCASE-001",
            "query": "I want to buy a pet. Check the inventory, find available ones, buy pet 12345, and mark it as sold.",
            "expected_tool_use": [

                {"tool_name": "get_inventory", "tool_input": {}},
                {"tool_name": "find_pets_by_status", "tool_input": {"status": "available"}},
                {"tool_name": "place_order", "tool_input": {"quantity": 1},"pet_id": 12345},
                {"tool_name": "place_order", "tool_input": {"quantity": 1, "pet_id": 12345}},
                {"tool_name": "update_pet_status", "tool_input": {"pet_id": 12345, "status": "sold", "name": "MockPet"}}
            ],
            "reference": ""
        }
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp:
        json.dump(golden_case, tmp)
        tmp_path = tmp.name

    logger.info(f"📂 Temporary dataset generated: {tmp_path}")

    # 3. Define the Network Mock (Network Simulator)
    # To evaluate TRACEABILITY, we need the agent not to fail due to network issues,
    # but to complete the flow to see if it chose the correct tools.
    async def mock_network_response(*args, **kwargs):
        call_str = str(args) + str(kwargs)
        
        if "inventory" in call_str: 
            return {"status": "success", "code": 200, "data": {"available": 50}}
        if "findByStatus" in call_str: 
            return {"status": "success", "code": 200, "data": [{"id": 12345, "name": "Fluffy", "status": "available"}]}
        if "order" in call_str: 
            return {"status": "success", "code": 200, "data": {"id": "ORD-123", "status": "placed"}}
        if "pet" in call_str: 
            return {"status": "success", "code": 200, "data": {"id": 12345, "status": "sold", "name": "Fluffy"}}
            
        return {"status": "success", "code": 200, "data": {"mock": "default"}}

    # 4. Controlled Execution (Dependency Injection + Patching)
    logger.info("⚙️  Iniciando Evaluador (Mock Mode, 1 Run)...")
    print("\n" + "-"*80)
    print(" 📊 ADK EVALUATION TABLE (Generated in real-time)")
    print("-"*80 + "\n")

    try:
        # A) Patch the network of the specific agent
        with patch('chaos_engine.agents.order_agent.chaos_proxy.send_request', side_effect=mock_network_response):
            
            # B) Patch the Evaluator to force a single execution (Determinism)
            original_eval_func = AgentEvaluator.evaluate_eval_set
            
            async def patched_eval(*args, **kwargs):
                kwargs['num_runs'] = 1  # Force 1 run
                kwargs['print_detailed_results'] = True # Force table printing
                return await original_eval_func(*args, **kwargs)

            # C) Ejecutamos con el parche aplicado
            with patch.object(AgentEvaluator, 'evaluate_eval_set', side_effect=patched_eval):
                
                result = await AgentEvaluator.evaluate(
                    agent_module="chaos_engine.agents.order_agent",
                    eval_dataset_file_path_or_dir=tmp_path
                )
                
    except Exception as e:
        logger.error(f"❌ Error during evaluation: {e}")
        raise e
    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            logger.info("🧹 Temporary files cleaned up.")

    # 5. Final Summary
    print("\n" + "="*80)
    if result:
        # Safely extract metrics
        results_list = result.eval_results if hasattr(result, 'eval_results') else result
        metrics = results_list[0].metrics if hasattr(results_list[0], 'metrics') else results_list[0]
        
        tool_score = metrics.get('tool_trajectory_avg_score') or metrics.get('tool_use_match', 0)
        
        if tool_score >= 0.8:
            print(f"✅ RESULT: COMPLETE SUCCESS (Score: {tool_score})")
            print("   The framework has certified that the agent followed the correct procedure.")
        else:
            print(f"⚠️ RESULT: REVIEW NEEDED (Score: {tool_score})")
    else:
        print("❌ RESULT: EXECUTION FAILED")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(run_showcase())