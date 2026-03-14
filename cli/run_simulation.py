"""
CLI script to run parametric experiments.
"""
from __future__ import annotations

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from chaos_engine.core.logging import setup_logger 
from chaos_engine.simulation.parametric import ParametricABTestRunner

def main():
    parser = argparse.ArgumentParser(description="Run parametric chaos experiments")
    
    parser.add_argument("--failure-rates", type=float, nargs="+", required=True)
    parser.add_argument("--experiments-per-rate", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42, help="Base seed for reproducibility (default: 42)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging to console")
    parser.add_argument("--playbook-baseline", type=str, default="assets/playbooks/baseline.json",
                        help="Path to baseline playbook JSON (default: assets/playbooks/baseline.json)")
    parser.add_argument("--playbook-training", type=str, default="assets/playbooks/training.json",
                        help="Path to training playbook JSON (default: assets/playbooks/training.json)")
    parser.add_argument("--simulate-delays", action="store_true",
                        help="Actually sleep during backoff delays (slow but realistic latency metrics)")

    args = parser.parse_args()
    
# 1. PREPARAR DIRECTORIO
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Usar resolve() para obtener ruta absoluta
    output_dir = (Path("reports") / "parametric_experiments" / f"run_{timestamp}").resolve()
    
    # 2. INICIALIZAR LOGGING
    logger = setup_logger("Experiment_log_", verbose=args.verbose, log_dir=str(output_dir))

    logger.info("="*70)
    logger.info("PARAMETRIC EXPERIMENT CONFIGURATION")
    logger.info("="*70)
    logger.info("Failure Rates: %s", args.failure_rates)
    logger.info("Experiments per rate: %d", args.experiments_per_rate)
    logger.info("Total experiments: %d (Baseline + Playbook)", len(args.failure_rates) * args.experiments_per_rate * 2)
    logger.info("Output directory: %s", output_dir)

    runner = ParametricABTestRunner(
        failure_rates=args.failure_rates,
        experiments_per_rate=args.experiments_per_rate,
        output_dir=output_dir,
        seed=args.seed,
        logger=logger,
        playbook_baseline_path=args.playbook_baseline,
        playbook_training_path=args.playbook_training,
        simulate_delays=args.simulate_delays,
    )
    
    
    asyncio.run(runner.run_parametric_experiments())

if __name__ == "__main__":
    main()