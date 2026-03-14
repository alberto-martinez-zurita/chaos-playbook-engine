"""Pydantic-based configuration models with validation.

Replaces raw dict-based config access with typed, validated models.
Supports loading from YAML files and environment variables.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class AgentSettings(BaseModel):
    """LLM agent configuration."""
    model: str = "gemini-2.5-flash-lite"


class ExperimentSettings(BaseModel):
    """Experiment defaults."""
    default_seed: int = Field(default=42, ge=0)


class SimulationSettings(BaseModel):
    """Parametric simulation configuration."""
    failure_rates: list[float] = Field(default_factory=lambda: [0.0, 0.1, 0.2, 0.3])
    experiments_per_rate: int = Field(default=50, ge=1)
    seed: int = Field(default=42, ge=0)
    playbook_baseline: str = "assets/playbooks/baseline.json"
    playbook_training: str = "assets/playbooks/training.json"
    simulate_delays: bool = False

    @field_validator("failure_rates", mode="before")
    @classmethod
    def _validate_rates(cls, v: Any) -> list[float]:
        if isinstance(v, (int, float)):
            v = [v]
        for rate in v:
            if not 0.0 <= rate <= 1.0:
                raise ValueError(f"failure_rate must be in [0, 1], got {rate}")
        return v


class AppSettings(BaseModel):
    """Top-level application settings.

    Can be constructed from a raw config dict (e.g. YAML) via::

        settings = AppSettings.from_yaml_dict(config)
    """
    environment: str = "dev"
    agent: AgentSettings = Field(default_factory=AgentSettings)
    experiment: ExperimentSettings = Field(default_factory=ExperimentSettings)
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)
    runner_type: str = "InMemoryRunner"
    mock_mode: bool = False
    use_vertex_ai: bool = False

    @classmethod
    def from_yaml_dict(cls, data: dict[str, Any]) -> AppSettings:
        """Build settings from a raw YAML-loaded dict, tolerating missing keys."""
        runner_type = data.get("runner", {}).get("type", "InMemoryRunner")
        return cls(
            environment=data.get("environment", "dev"),
            agent=AgentSettings(**data["agent"]) if "agent" in data else AgentSettings(),
            experiment=ExperimentSettings(**data["experiment"]) if "experiment" in data else ExperimentSettings(),
            simulation=SimulationSettings(**data["simulation"]) if "simulation" in data else SimulationSettings(),
            runner_type=runner_type,
            mock_mode=data.get("mock_mode", False),
            use_vertex_ai=data.get("use_vertex_ai", False),
        )
