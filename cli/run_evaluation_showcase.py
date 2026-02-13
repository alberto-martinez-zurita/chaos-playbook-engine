"""
run_evaluation_showcase.py
==========================
Script de Demostración de Capacidades de Observabilidad (Google ADK).

Este script no ejecuta un experimento de caos masivo.
Su objetivo es demostrar cómo el framework puede:
1. Evaluar la calidad de la respuesta del agente.
2. Validar la trayectoria de uso de herramientas (Tool Trajectory).
3. Generar reportes detallados en formato tabla.

Uso:
    poetry run python cli/run_evaluation_showcase.py
"""

import sys
import asyncio
import json
import tempfile
import os
import logging
from pathlib import Path
from unittest.mock import patch

# Añadir src al path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

# Importaciones del Framework
from google.adk.evaluation.agent_evaluator import AgentEvaluator
from chaos_engine.core.config import load_config
from chaos_engine.core.logging import setup_logger

# Aseguramos que el módulo del agente esté cargado para el patching
import chaos_engine.agents.order_agent

async def run_showcase():
    # 1. Configuración Básica
    logger = setup_logger("adk_showcase", verbose=True)
    logger.info("="*80)
    logger.info("🚀 GOOGLE ADK OBSERVABILITY SHOWCASE")
    logger.info("="*80)
    
    # 2. Definir el 'Golden Dataset' (El caso de prueba ideal)
    # Lo creamos temporalmente para que el ADK lo lea
    golden_case = [
        {
            "id": "SHOWCASE-001",
            "query": "Quiero comprar una mascota. Revisa el inventario, busca disponibles, compra la 12345 y marca como vendida.",
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

    logger.info(f"📂 Dataset temporal generado: {tmp_path}")

    # 3. Definir el Mock de Red (Network Simulator)
    # Para evaluar la TRAZABILIDAD, necesitamos que el agente no falle por red,
    # sino que complete el flujo para ver si eligió las herramientas correctas.
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

    # 4. Ejecución Controlada (Inyección de Dependencias + Patching)
    logger.info("⚙️  Iniciando Evaluador (Mock Mode, 1 Run)...")
    print("\n" + "-"*80)
    print(" 📊 TABLA DE EVALUACIÓN ADK (Generada en tiempo real)")
    print("-"*80 + "\n")

    try:
        # A) Parcheamos la red del agente específico
        with patch('chaos_engine.agents.order_agent.chaos_proxy.send_request', side_effect=mock_network_response):
            
            # B) Parcheamos el Evaluador para forzar 1 sola ejecución (Determinismo)
            original_eval_func = AgentEvaluator.evaluate_eval_set
            
            async def patched_eval(*args, **kwargs):
                kwargs['num_runs'] = 1  # Forzamos 1 run
                kwargs['print_detailed_results'] = True # Forzamos impresión de tabla
                return await original_eval_func(*args, **kwargs)

            # C) Ejecutamos con el parche aplicado
            with patch.object(AgentEvaluator, 'evaluate_eval_set', side_effect=patched_eval):
                
                result = await AgentEvaluator.evaluate(
                    agent_module="chaos_engine.agents.order_agent",
                    eval_dataset_file_path_or_dir=tmp_path
                )
                
    except Exception as e:
        logger.error(f"❌ Error durante la evaluación: {e}")
        raise e
    finally:
        # Limpieza
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            logger.info("🧹 Archivos temporales limpiados.")

    # 5. Resumen Final
    print("\n" + "="*80)
    if result:
        # Extraer métricas de forma segura
        results_list = result.eval_results if hasattr(result, 'eval_results') else result
        metrics = results_list[0].metrics if hasattr(results_list[0], 'metrics') else results_list[0]
        
        tool_score = metrics.get('tool_trajectory_avg_score') or metrics.get('tool_use_match', 0)
        
        if tool_score >= 0.8:
            print(f"✅ RESULTADO: ÉXITO ROTUNDO (Score: {tool_score})")
            print("   El framework ha certificado que el agente siguió el procedimiento correcto.")
        else:
            print(f"⚠️ RESULTADO: REVISIÓN NECESARIA (Score: {tool_score})")
    else:
        print("❌ RESULTADO: FALLO EN EJECUCIÓN")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(run_showcase())