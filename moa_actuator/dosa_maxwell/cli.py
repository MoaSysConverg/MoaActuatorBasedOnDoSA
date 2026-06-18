from __future__ import annotations

import argparse
import json
from pathlib import Path

from .maxwell_runner import run_maxwell_2d, run_maxwell_3d, to_dict
from .parser import parse_dosa_file
from .profiles import get_unified_plan_summary, list_profiles


def _cmd_inspect(args: argparse.Namespace) -> int:
    design = parse_dosa_file(args.input)
    payload = {
        "name": design.name,
        "source_file": design.source_file,
        "source_type": design.source_type,
        "node_count": len(design.nodes),
        "part_count": len(design.parts),
        "test_count": len(design.tests),
    }
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_export_json(args: argparse.Namespace) -> int:
    design = parse_dosa_file(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(design.model_dump_json(indent=2), encoding="utf-8")
    print(f"Exported: {out_path}")
    return 0


def _cmd_run_2d(args: argparse.Namespace) -> int:
    design = parse_dosa_file(args.input)
    result = run_maxwell_2d(design, args.out_dir, dry_run=args.dry_run, profile_name=args.profile)
    print(json.dumps(to_dict(result), indent=2))
    return 0 if result.ok else 1


def _cmd_run_3d(args: argparse.Namespace) -> int:
    design = parse_dosa_file(args.input)
    result = run_maxwell_3d(design, args.out_dir, dry_run=args.dry_run, profile_name=args.profile)
    print(json.dumps(to_dict(result), indent=2))
    return 0 if result.ok else 1


def _cmd_profiles(_: argparse.Namespace) -> int:
    print(json.dumps(list_profiles(), indent=2))
    return 0


def _cmd_plan(_: argparse.Namespace) -> int:
    print(json.dumps(get_unified_plan_summary(), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dosa-maxwell", description="DoSA to Maxwell automation")
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect", help="Inspect DoSA file summary")
    p_inspect.add_argument("--input", required=True, help="Path to .dsa or .dsa3d file")
    p_inspect.set_defaults(func=_cmd_inspect)

    p_export = sub.add_parser("export-json", help="Export canonical JSON")
    p_export.add_argument("--input", required=True)
    p_export.add_argument("--output", required=True)
    p_export.set_defaults(func=_cmd_export_json)

    p_run2d = sub.add_parser("run-2d", help="Run Maxwell2d workflow")
    p_run2d.add_argument("--input", required=True)
    p_run2d.add_argument("--out-dir", required=True)
    p_run2d.add_argument("--dry-run", action="store_true", default=False)
    p_run2d.add_argument("--profile", default="default", help="Execution profile name")
    p_run2d.set_defaults(func=_cmd_run_2d)

    p_run3d = sub.add_parser("run-3d", help="Run Maxwell3d workflow")
    p_run3d.add_argument("--input", required=True)
    p_run3d.add_argument("--out-dir", required=True)
    p_run3d.add_argument("--dry-run", action="store_true", default=False)
    p_run3d.add_argument("--profile", default="default", help="Execution profile name")
    p_run3d.set_defaults(func=_cmd_run_3d)

    p_profiles = sub.add_parser("profiles", help="List available execution profiles")
    p_profiles.set_defaults(func=_cmd_profiles)

    p_plan = sub.add_parser("plan", help="Show unified development plan summary")
    p_plan.set_defaults(func=_cmd_plan)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
