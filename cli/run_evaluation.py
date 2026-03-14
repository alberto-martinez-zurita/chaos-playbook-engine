"""
CLI entry point for Agent Evaluation with Observability.
"""
from __future__ import annotations

import sys
import asyncio
import argparse
import json
from pathlib import Path
from datetime import datetime

# Setup path (if not installed)
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from chaos_engine.evaluation.runner import EvaluationRunner
from chaos_engine.core.logging import setup_logger

async def main():
    parser = argparse.ArgumentParser(description="Run Chaos Agent Evaluation Suite")
    parser.add_argument("--suite", type=str, default="assets/evaluations/test_suite.json")
    parser.add_argument("--playbook", type=str, default="assets/playbooks/training.json")
    parser.add_argument("--verbose", action="store_true", help="Show logs in console")
    
    args = parser.parse_args()
    
    # 1. PREPARE OBSERVABILITY
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Define nested path in 'reports'
    output_dir = project_root / "reports" / "evaluations" / f"eval_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Explicitly pass log_dir=str(output_dir)
    # If this argument is missing, it defaults to /logs
    logger = setup_logger("evaluation", verbose=args.verbose, log_dir=str(output_dir))
     
    logger.info("="*60)
    logger.info("🕵️‍♂️ AGENT QA EVALUATION STARTED")
    logger.info(f"📁 Report Artifacts: {output_dir}")
    logger.info("="*60)

    # Validate paths
    suite_path = Path(args.suite)
    if not suite_path.exists(): suite_path = project_root / args.suite
    
    playbook_path = args.playbook
    if not Path(playbook_path).exists(): playbook_path = str(project_root / args.playbook)

    # 2. EXECUTE
    runner = EvaluationRunner(agent_playbook=playbook_path)
    results = await runner.run_suite(str(suite_path))
    
    # 3. GENERATE JSON REPORT (Quality Artifact)
    report = {
        "timestamp": timestamp,
        "suite": args.suite,
        "playbook": args.playbook,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed)
        },
        "results": [r.to_dict() for r in results]
    }
    
    json_path = output_dir / "evaluation_report.json"
    with open(json_path, 'w') as f:
        json.dump(report, f, indent=2)
        
    logger.info(f"\n📊 REPORT SAVED: {json_path}")
    logger.info(f"✅ PASSED: {report['summary']['passed']}/{report['summary']['total']}")
    
    if report['summary']['failed'] > 0:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())