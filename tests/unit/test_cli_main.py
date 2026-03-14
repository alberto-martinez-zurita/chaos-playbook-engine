"""Tests for the unified CLI (__main__.py)."""
from __future__ import annotations

import sys

import pytest

from chaos_engine.__main__ import build_parser


def test_parser_simulate_subcommand():
    parser = build_parser()
    args = parser.parse_args(["simulate", "--failure-rates", "0.1", "0.2", "--seed", "99"])
    assert args.command == "simulate"
    assert args.failure_rates == [0.1, 0.2]
    assert args.seed == 99


def test_parser_judge_subcommand():
    parser = build_parser()
    args = parser.parse_args(["judge", "--input", "results.csv", "--compare", "existing.json"])
    assert args.command == "judge"
    assert args.input == "results.csv"
    assert args.compare == "existing.json"


def test_parser_registry_list():
    parser = build_parser()
    args = parser.parse_args(["registry", "list", "--registry-dir", "/tmp/reg"])
    assert args.command == "registry"
    assert args.registry_command == "list"
    assert args.registry_dir == "/tmp/reg"


def test_parser_registry_promote():
    parser = build_parser()
    args = parser.parse_args([
        "registry", "promote", "--version", "1.0.0",
        "--validated-by", "admin", "--min-success-rate", "0.9",
        "--actual-success-rate", "0.95",
    ])
    assert args.version == "1.0.0"
    assert args.validated_by == "admin"
    assert args.min_success_rate == 0.9
    assert args.actual_success_rate == 0.95


def test_parser_simulate_agents_flag():
    parser = build_parser()
    args = parser.parse_args([
        "simulate", "--failure-rates", "0.1",
        "--agents", "aggressive:path/a.json", "conservative:path/c.json",
    ])
    assert args.agents == ["aggressive:path/a.json", "conservative:path/c.json"]


def test_parser_no_command(capsys):
    parser = build_parser()
    args = parser.parse_args([])
    assert args.command is None
