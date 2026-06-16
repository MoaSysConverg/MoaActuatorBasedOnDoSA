"""Command-line interface for moa_actuator."""

from __future__ import annotations

import argparse
import json
import sys

from .parser import parse_dosa_file
from .profiles import get_unified_plan_summary, list_profiles
from .runner import RunConfig, run


def _cmd_inspect(args: argparse.Namespace) -> int:
    design = parse_dosa_file(args.input)
    payload = {
        "name": design.name,
        "source_file": design.source_file,
        "source_type": design.source_type,
        "node_count": len(design.nodes),
        "part_count": len(design.parts),
        "test_count": len(design.tests),
        "parts": [{"name": p.name, "kind": p.kind} for p in design.parts],
        "tests": [{"name": t.name, "kind": t.kind} for t in design.tests],
    }
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    config = RunConfig(
        input_file=args.input,
        mode=args.mode,
        solver=args.solver,
        profile=args.profile,
        out_dir=args.out_dir,
        dry_run=args.dry_run,
        non_graphical=not args.graphical,
    )
    result = run(config)
    payload = {
        "ok": result.ok,
        "mode": result.mode,
        "solver": result.solver,
        "commands_count": len(result.commands),
        "errors": result.errors,
    }
    if result.project_path:
        payload["project_path"] = result.project_path
    print(json.dumps(payload, indent=2))
    return 0 if result.ok else 1


def _cmd_profiles(_: argparse.Namespace) -> int:
    print(json.dumps(list_profiles(), indent=2))
    return 0


def _cmd_plan(_: argparse.Namespace) -> int:
    print(json.dumps(get_unified_plan_summary(), indent=2))
    return 0


def _cmd_gui(_: argparse.Namespace) -> int:
    try:
        from .gui.app import launch
        launch()
        return 0
    except ImportError as e:
        print(f"GUI requires PyQt6: {e}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="moa-actuator",
        description="MoA Actuator — DoSA 2D/3D Maxwell/FEMM/GetDP automation",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # inspect
    p_inspect = sub.add_parser("inspect", help="Inspect a DoSA file")
    p_inspect.add_argument("--input", required=True, help="Path to .dsa or .dsa3d file")
    p_inspect.set_defaults(func=_cmd_inspect)

    # run
    p_run = sub.add_parser("run", help="Run simulation")
    p_run.add_argument("--input", required=True, help="Path to .dsa or .dsa3d file")
    p_run.add_argument("--mode", choices=["2d", "3d"], default="2d")
    p_run.add_argument("--solver", choices=["maxwell", "femm", "getdp"], default="maxwell")
    p_run.add_argument("--profile", default="default", help="Simulation profile name")
    p_run.add_argument("--out-dir", default="./output", help="Output directory")
    p_run.add_argument("--dry-run", action="store_true", help="Generate commands without executing")
    p_run.add_argument("--graphical", action="store_true", help="Show AEDT GUI")
    p_run.set_defaults(func=_cmd_run)

    # profiles
    p_profiles = sub.add_parser("profiles", help="List available profiles")
    p_profiles.set_defaults(func=_cmd_profiles)

    # plan
    p_plan = sub.add_parser("plan", help="Show unified plan status")
    p_plan.set_defaults(func=_cmd_plan)

    # gui
    p_gui = sub.add_parser("gui", help="Launch PyQt6 GUI")
    p_gui.set_defaults(func=_cmd_gui)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)
