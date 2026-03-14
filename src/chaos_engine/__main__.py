"""Unified CLI entry point for chaos-engine.

Usage::

    python -m chaos_engine simulate --failure-rates 0.1 0.2 --experiments 50
    python -m chaos_engine judge --input reports/run_xyz/raw_results.csv
    python -m chaos_engine registry list
    python -m chaos_engine registry promote --version 1.0.0
"""
from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from datetime import datetime
from pathlib import Path


def _cmd_simulate(args: argparse.Namespace) -> None:
    """Run parametric chaos experiments."""
    from chaos_engine.core.logging import setup_logger
    from chaos_engine.simulation.parametric import AgentConfig, ParametricABTestRunner

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = (Path("reports") / "parametric_experiments" / f"run_{timestamp}").resolve()

    logger = setup_logger("chaos_engine", verbose=args.verbose, log_dir=str(output_dir))

    # Build agent configs
    agents = None
    if args.agents:
        agents = []
        for spec in args.agents:
            name, path = spec.split(":", 1)
            agents.append(AgentConfig(name=name, playbook_path=path))

    runner = ParametricABTestRunner(
        failure_rates=args.failure_rates,
        experiments_per_rate=args.experiments_per_rate,
        output_dir=output_dir,
        seed=args.seed,
        logger=logger,
        playbook_baseline_path=args.playbook_baseline,
        playbook_training_path=args.playbook_training,
        simulate_delays=args.simulate_delays,
        agents=agents,
    )

    result = asyncio.run(runner.run_parametric_experiments())
    logger.info("Done. Total experiments: %d", result["total_experiments"])
    print(f"Results saved to {output_dir}")


def _cmd_judge(args: argparse.Namespace) -> None:
    """Analyze experiment results and generate candidate playbook."""
    from chaos_engine.agents.playbook_writer import PlaybookWriterAgent

    writer = PlaybookWriterAgent(min_samples=args.min_samples)
    candidate = writer.analyze(args.input)

    output_path = args.output or str(Path(args.input).parent / "candidate_playbook.json")
    writer.save(candidate, output_path)

    if args.compare:
        diff = writer.compare_with_existing(candidate, args.compare)
        print(f"Comparison with {args.compare}:")
        print(f"  New entries:       {len(diff['new'])} {diff['new']}")
        print(f"  Changed entries:   {len(diff['changed'])} {diff['changed']}")
        print(f"  Unchanged entries: {len(diff['unchanged'])}")

    print(f"Candidate playbook saved to {output_path}")


def _cmd_evolve(args: argparse.Namespace) -> None:
    """Run playbook evolution (mutation + selection)."""
    from chaos_engine.simulation.mutation import PlaybookEvolver

    evolver = PlaybookEvolver(
        base_playbook_path=args.playbook,
        failure_rates=args.failure_rates,
        experiments_per_rate=args.experiments_per_rate,
        seed=args.seed,
        output_dir=args.output_dir,
        mutation_rate=args.mutation_rate,
    )
    best = asyncio.run(evolver.evolve(
        generations=args.generations,
        variants_per_gen=args.variants,
    ))
    print(f"Best variant: {best.variant_id} (score={best.score:.2f}, success={best.success_rate:.1%})")
    print(f"Saved to {args.output_dir}/best_playbook.json")


def _cmd_registry_list(args: argparse.Namespace) -> None:
    """List all registered playbook versions."""
    from chaos_engine.core.playbook_registry import PlaybookRegistry

    registry = PlaybookRegistry(args.registry_dir)
    versions = registry.list_versions()

    if not versions:
        print("No playbook versions registered.")
        return

    current = registry.get_current()
    current_version = current.metadata.version if current else None

    for v in versions:
        marker = " (current)" if v.lstrip("v") == current_version else ""
        pb = registry.get(v.lstrip("v"))
        print(f"  {v}  stage={pb.metadata.stage}{marker}")


def _cmd_registry_promote(args: argparse.Namespace) -> None:
    """Promote a playbook version to the next lifecycle stage."""
    from chaos_engine.core.playbook_registry import PlaybookRegistry

    registry = PlaybookRegistry(args.registry_dir)
    promoted = registry.promote(
        version=args.version,
        validated_by=args.validated_by,
        min_success_rate=args.min_success_rate,
        actual_success_rate=args.actual_success_rate,
    )
    print(f"Promoted v{args.version} to {promoted.metadata.stage}")


def _cmd_registry_register(args: argparse.Namespace) -> None:
    """Register a new playbook version from file."""
    from chaos_engine.core.playbook_registry import PlaybookRegistry, VersionedPlaybook

    registry = PlaybookRegistry(args.registry_dir)
    playbook = VersionedPlaybook.from_file(args.file)
    path = registry.register(playbook)
    print(f"Registered v{playbook.metadata.version} at {path}")


def build_parser() -> argparse.ArgumentParser:
    """Build the unified CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="chaos-engine",
        description="Chaos Playbook Engine — resilience testing and playbook management",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- simulate ---
    sim = subparsers.add_parser("simulate", help="Run parametric chaos experiments")
    sim.add_argument("--failure-rates", type=float, nargs="+", required=True)
    sim.add_argument("--experiments-per-rate", type=int, default=5)
    sim.add_argument("--seed", type=int, default=42)
    sim.add_argument("--verbose", action="store_true")
    sim.add_argument("--playbook-baseline", default="assets/playbooks/baseline.json")
    sim.add_argument("--playbook-training", default="assets/playbooks/training.json")
    sim.add_argument("--simulate-delays", action="store_true")
    sim.add_argument(
        "--agents", nargs="+", metavar="NAME:PATH",
        help="Agent configs as name:playbook_path pairs (overrides baseline/training)",
    )
    sim.set_defaults(func=_cmd_simulate)

    # --- judge ---
    judge = subparsers.add_parser("judge", help="Analyze results and generate candidate playbook")
    judge.add_argument("--input", "-i", required=True, help="Path to raw_results.csv")
    judge.add_argument("--output", "-o", help="Output path for candidate playbook JSON")
    judge.add_argument("--compare", help="Existing playbook to compare against")
    judge.add_argument("--min-samples", type=int, default=5, help="Min samples per pattern")
    judge.set_defaults(func=_cmd_judge)

    # --- evolve ---
    evolve = subparsers.add_parser("evolve", help="Evolve playbook via mutation and selection")
    evolve.add_argument("--playbook", required=True, help="Base playbook to evolve")
    evolve.add_argument("--failure-rates", type=float, nargs="+", default=[0.1, 0.3, 0.5])
    evolve.add_argument("--experiments-per-rate", type=int, default=20)
    evolve.add_argument("--generations", type=int, default=3, help="Number of evolution generations")
    evolve.add_argument("--variants", type=int, default=4, help="Variants per generation")
    evolve.add_argument("--mutation-rate", type=float, default=0.3, help="Probability of mutating each entry")
    evolve.add_argument("--seed", type=int, default=42)
    evolve.add_argument("--output-dir", default="reports/evolution")
    evolve.set_defaults(func=_cmd_evolve)

    # --- registry ---
    reg = subparsers.add_parser("registry", help="Manage playbook versions")
    reg_sub = reg.add_subparsers(dest="registry_command")

    reg_list = reg_sub.add_parser("list", help="List all registered versions")
    reg_list.add_argument("--registry-dir", default="data/playbook_registry")
    reg_list.set_defaults(func=_cmd_registry_list)

    reg_promote = reg_sub.add_parser("promote", help="Promote a version to next stage")
    reg_promote.add_argument("--version", required=True)
    reg_promote.add_argument("--validated-by", default="cli")
    reg_promote.add_argument("--min-success-rate", type=float, default=None)
    reg_promote.add_argument("--actual-success-rate", type=float, default=None)
    reg_promote.add_argument("--registry-dir", default="data/playbook_registry")
    reg_promote.set_defaults(func=_cmd_registry_promote)

    reg_register = reg_sub.add_parser("register", help="Register a new playbook version")
    reg_register.add_argument("--file", required=True, help="Path to playbook JSON file")
    reg_register.add_argument("--registry-dir", default="data/playbook_registry")
    reg_register.set_defaults(func=_cmd_registry_register)

    return parser


def _install_signal_handlers() -> None:
    """Install graceful shutdown handlers for SIGINT/SIGTERM."""
    def _handler(signum: int, _frame: object) -> None:
        name = signal.Signals(signum).name
        print(f"\nReceived {name}. Shutting down gracefully...")
        sys.exit(128 + signum)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def main() -> None:
    _install_signal_handlers()

    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "registry" and not getattr(args, "registry_command", None):
        parser.parse_args(["registry", "--help"])
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
