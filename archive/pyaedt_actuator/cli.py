from __future__ import annotations

import argparse

from .config import ActuatorPaths, MaxwellSettings, SweepSettings
from .runner import ActuatorSimulationRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run actuator Maxwell workflows"
    )
    parser.add_argument(
        "--notebook-path",
        required=True,
        help="Folder where .aedt project lives",
    )
    parser.add_argument(
        "--project-name",
        required=True,
        help="AEDT project name without extension",
    )
    parser.add_argument(
        "--design-name",
        default="01_Actuator",
        help="Target design name",
    )
    parser.add_argument(
        "--solution-type",
        default="MagnetostaticZ",
        help="Requested solution type",
    )
    parser.add_argument(
        "--aedt-version",
        default="2026.1",
        help="AEDT version",
    )
    parser.add_argument(
        "--non-graphical",
        action="store_true",
        help="Run without GUI",
    )
    parser.add_argument(
        "--workflow",
        choices=["magnetostatic", "transient"],
        default="magnetostatic",
        help="Workflow to run",
    )
    parser.add_argument(
        "--cores",
        type=int,
        default=8,
        help="Cores for parametric run",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    paths = ActuatorPaths(
        notebook_path=args.notebook_path,
        project_name=args.project_name,
        design_name=args.design_name,
    )
    settings = MaxwellSettings(
        aedt_version=args.aedt_version,
        non_graphical=args.non_graphical,
        solution_type=args.solution_type,
    )

    runner = ActuatorSimulationRunner(
        paths=paths,
        settings=settings,
        sweep=SweepSettings(),
    )

    if args.workflow == "magnetostatic":
        rows = runner.run_magnetostatic_pipeline(cores=args.cores)
        print(f"Magnetostatic workflow done. Rows: {len(rows)}")
    else:
        plots = runner.run_transient_pipeline()
        print(f"Transient workflow done. Plots: {list(plots.keys())}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
