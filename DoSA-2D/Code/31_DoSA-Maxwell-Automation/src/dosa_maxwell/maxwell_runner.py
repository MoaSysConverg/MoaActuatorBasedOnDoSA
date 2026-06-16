from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .maxwell_builder import MaxwellSessionBuilder
from .models import DesignModel
from .profiles import MaxwellProfile, get_profile


@dataclass
class RunResult:
    ok: bool
    mode: str
    message: str
    output_file: str


def _write_result(out_dir: Path, payload: dict) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "run_result.json"
    output_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return str(output_path)


def run_maxwell_2d(
    design: DesignModel,
    out_dir: str | Path,
    dry_run: bool = True,
    profile_name: str = "default",
) -> RunResult:
    out_path = Path(out_dir)
    profile: MaxwellProfile = get_profile(profile_name)

    builder = MaxwellSessionBuilder(
        design=design,
        profile=profile,
        out_dir=out_path,
        mode="2d",
        non_graphical=True,
    )
    result = builder.build(live=not dry_run)

    payload = {
        "ok": result.ok,
        "mode": "2d",
        "dry_run": dry_run,
        "live_session": result.live,
        "profile": asdict(profile),
        "design_name": design.name,
        "parts": len(design.parts),
        "tests": len(design.tests),
        "commands_count": len(result.commands),
        "errors": result.errors,
        "message": (
            f"Build complete. {len(result.commands)} commands recorded."
            + (f" {len(result.errors)} errors." if result.errors else "")
        ),
    }
    file_name = _write_result(out_path, payload)
    return RunResult(ok=result.ok, mode="2d", message=payload["message"], output_file=file_name)


def run_maxwell_3d(
    design: DesignModel,
    out_dir: str | Path,
    dry_run: bool = True,
    profile_name: str = "default",
) -> RunResult:
    out_path = Path(out_dir)
    profile: MaxwellProfile = get_profile(profile_name)

    builder = MaxwellSessionBuilder(
        design=design,
        profile=profile,
        out_dir=out_path,
        mode="3d",
        non_graphical=True,
    )
    result = builder.build(live=not dry_run)

    payload = {
        "ok": result.ok,
        "mode": "3d",
        "dry_run": dry_run,
        "live_session": result.live,
        "profile": asdict(profile),
        "design_name": design.name,
        "parts": len(design.parts),
        "tests": len(design.tests),
        "commands_count": len(result.commands),
        "errors": result.errors,
        "message": (
            f"Build complete. {len(result.commands)} commands recorded."
            + (f" {len(result.errors)} errors." if result.errors else "")
        ),
    }
    file_name = _write_result(out_path, payload)
    return RunResult(ok=result.ok, mode="3d", message=payload["message"], output_file=file_name)


def to_dict(result: RunResult) -> dict:
    return asdict(result)
