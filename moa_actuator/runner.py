"""Unified pipeline runner — orchestrates solver execution for DoSA designs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import DesignModel
from .parser import parse_dosa_file
from .profiles import MaxwellProfile, get_profile
from .setup import SweepSettings
from .solvers.base import SolveResult, SolverBackend
from .solvers.maxwell_backend import MaxwellBackend


@dataclass
class RunConfig:
    """Configuration for a simulation run."""

    input_file: str | Path | None = None
    design: DesignModel | None = None
    mode: str = "2d"  # "2d" or "3d"
    solver: str = "maxwell"  # "maxwell", "femm", "getdp"
    profile: str = "default"
    out_dir: str = "./output"
    dry_run: bool = False
    aedt_version: str = "2026.1"
    non_graphical: bool = True


def get_solver_backend(config: RunConfig) -> SolverBackend:
    """Instantiate the appropriate solver backend."""
    if config.solver == "maxwell":
        profile = get_profile(config.profile)
        return MaxwellBackend(
            aedt_version=config.aedt_version,
            non_graphical=config.non_graphical,
            solution_type=profile.solution_type,
        )
    elif config.solver == "femm":
        from .solvers.femm_backend import FemmBackend
        return FemmBackend()
    elif config.solver == "getdp":
        from .solvers.getdp_backend import GetDPBackend
        return GetDPBackend()
    else:
        raise ValueError(f"Unknown solver: {config.solver}")


def run(config: RunConfig) -> SolveResult:
    """Execute a simulation run with the given configuration."""
    # Load design
    if config.design is not None:
        design = config.design
    elif config.input_file is not None:
        design = parse_dosa_file(config.input_file)
    else:
        raise ValueError("Either input_file or design must be provided")

    # Auto-detect mode from file type if not explicitly set
    if design.source_type == "dsa3d" and config.mode == "2d":
        config.mode = "3d"

    # Get solver
    backend = get_solver_backend(config)

    if not backend.supports_mode(config.mode):
        return SolveResult(
            ok=False,
            mode=config.mode,
            solver=backend.name,
            errors=[f"Solver '{backend.name}' does not support mode '{config.mode}'"],
        )

    # Execute
    profile = get_profile(config.profile)
    return backend.solve(
        design=design,
        mode=config.mode,
        out_dir=config.out_dir,
        dry_run=config.dry_run,
        stop_time=profile.stop_time,
        time_step=profile.time_step,
    )
