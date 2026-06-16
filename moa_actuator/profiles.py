"""Profile management system for simulation presets.

Profiles define solver settings (solution type, time step, mesh hint)
loaded from config/unified_plan.json.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class MaxwellProfile:
    name: str
    source_pdf: str
    solution_type: str
    time_step: str
    stop_time: str
    mesh_hint: str
    notes: str


PLAN_PATH = Path(__file__).resolve().parent / "config" / "unified_plan.json"


def _load_profiles() -> dict[str, MaxwellProfile]:
    if not PLAN_PATH.exists():
        raise FileNotFoundError(f"Unified plan file not found: {PLAN_PATH}")

    payload = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    raw_profiles = payload.get("profiles", [])
    loaded: dict[str, MaxwellProfile] = {}

    for raw in raw_profiles:
        profile = MaxwellProfile(**raw)
        loaded[profile.name.strip().lower()] = profile

    return loaded


def _load_plan_summary() -> dict:
    if not PLAN_PATH.exists():
        raise FileNotFoundError(f"Unified plan file not found: {PLAN_PATH}")
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def get_profile(name: str) -> MaxwellProfile:
    """Get a named simulation profile."""
    profiles = _load_profiles()
    key = name.strip().lower()
    if key not in profiles:
        available = ", ".join(sorted(profiles))
        raise ValueError(f"Unknown profile '{name}'. Available profiles: {available}")
    return profiles[key]


def list_profiles() -> list[dict[str, str]]:
    """List all available profiles."""
    profiles = _load_profiles()
    return [asdict(p) for p in profiles.values()]


def get_unified_plan_summary() -> dict:
    """Get the unified plan overview."""
    plan = _load_plan_summary()
    return {
        "version": plan.get("version", ""),
        "scope": plan.get("scope", ""),
        "sources": plan.get("sources", {}),
        "milestones": plan.get("milestones", []),
    }
