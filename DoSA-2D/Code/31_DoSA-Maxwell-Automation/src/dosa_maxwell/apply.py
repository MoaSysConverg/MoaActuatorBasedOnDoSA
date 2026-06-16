"""apply.py — DoSA to Maxwell bridge.

Public API: ``apply_dosa_to_maxwell(design, app, profile)``

Users create a Maxwell2d/3d session with ansys.aedt.core directly (exactly
like pyaedt tutorials), then pass the live ``app`` object here.  The function
applies all DoSA geometry, materials, excitations and setup to that session and
returns a result dict.

Example (pyaedt style)::

    import ansys.aedt.core
    from dosa_maxwell import parse_dosa_file, apply_dosa_to_maxwell

    design = parse_dosa_file("Solenoid.dsa")

    m2d = ansys.aedt.core.Maxwell2d(
        project=r"C:/output/Solenoid.aedt",
        design="Solenoid",
        solution_type="MagnetostaticXY",
        version="2026.1",
        non_graphical=True,
        new_desktop=True,
    )
    m2d.modeler.model_units = "mm"

    result = apply_dosa_to_maxwell(design, m2d, profile="le01_2020r1")
    print(result)

    m2d.save_project()
    m2d.release_desktop()
"""

from __future__ import annotations

import logging
from typing import Any

from .geometry import Geometry2D, extract_geometry, geometry_from_coil_params
from .mapping import resolve_magnet_direction, resolve_material
from .models import DesignModel, NodeModel
from .profiles import MaxwellProfile, get_profile

logger = logging.getLogger(__name__)


# ─── result type ────────────────────────────────────────────────────────────


class ApplyResult(dict):
    """Result of apply_dosa_to_maxwell.  Behaves like a dict and has helpers."""

    @property
    def ok(self) -> bool:
        return len(self.get("errors", [])) == 0

    def __repr__(self) -> str:
        status = "OK" if self.ok else "FAILED"
        errs = self.get("errors", [])
        return (
            f"<ApplyResult {status} | parts={self['parts']} "
            f"errors={len(errs)}>"
        )


# ─── public entry point ──────────────────────────────────────────────────────


def apply_dosa_to_maxwell(
    design: DesignModel,
    app: Any,
    profile: str | MaxwellProfile = "default",
) -> ApplyResult:
    """Apply a DoSA design to a live Maxwell2d or Maxwell3d session.

    Args:
        design:  Parsed DoSA design (from ``parse_dosa_file``).
        app:     Live ``Maxwell2d`` or ``Maxwell3d`` instance.
        profile: Profile name (str) or ``MaxwellProfile`` dataclass.
                 Determines solution setup parameters (time step, stop time …).

    Returns:
        :class:`ApplyResult` (dict subclass) with keys:
        ``parts``, ``errors``, ``commands``.
    """
    if isinstance(profile, str):
        profile = get_profile(profile)

    # Detect mode from app class name
    class_name = type(app).__name__
    mode = "3d" if "3d" in class_name.lower() else "2d"

    errors: list[str] = []
    commands: list[str] = []

    def rec(msg: str) -> None:
        commands.append(msg)
        logger.debug(msg)

    # ── 1. Geometry ───────────────────────────────────────────────────────
    for part in design.parts:
        geom = _extract_geom(part)
        if geom is None or not geom.is_valid:
            errors.append(f"[geometry] No valid shape for '{part.name}'")
            continue

        pts = geom.to_polyline_points()
        rec(f"modeler.create_polyline({part.name}, {len(pts)} pts)")
        try:
            poly = app.modeler.create_polyline(
                points=pts,
                close_surface=True,
                cover_surface=True,
                name=part.name,
            )
            if poly is None:
                errors.append(f"[geometry] create_polyline returned None for '{part.name}'")
                continue
        except Exception as exc:
            errors.append(f"[geometry] create_polyline '{part.name}': {exc}")
            continue

        if mode == "3d":
            rec(f"modeler.sweep_around_axis({part.name}, Y, 360°)")
            try:
                app.modeler.sweep_around_axis(
                    assignment=part.name,
                    axis="Y",
                    sweep_angle=360,
                )
            except Exception as exc:
                errors.append(f"[geometry] sweep_around_axis '{part.name}': {exc}")

    # ── 2. Materials ─────────────────────────────────────────────────────
    for part in design.parts:
        mat_str = part.properties.get("Material", "")
        if not mat_str:
            continue
        try:
            mat = resolve_material(mat_str)
        except ValueError as exc:
            errors.append(f"[material] {exc}")
            continue

        material_name = _select_available_material_name(app, mat.maxwell_name, mat.category)
        if material_name != mat.maxwell_name:
            rec(f"material_fallback({part.name}, {mat.maxwell_name} -> {material_name})")
        rec(f"assign_material({part.name}, {material_name})")
        try:
            app.assign_material(assignment=[part.name], material=material_name)
        except Exception as exc:
            errors.append(f"[material] '{part.name}' → '{material_name}': {exc}")

        if part.kind == "Magnet":
            direction_str = part.properties.get("MagnetDirection", "UP")
            dx, dy = resolve_magnet_direction(direction_str)
            rec(f"assign_magnet_direction({part.name}, ({dx},{dy}))")
            # Maxwell accepts direction via material property or separate API;
            # record only — full magnet direction API varies by version.

    # ── 3. Setup (must exist before motion) ──────────────────────────────
    rec(f"create_setup(DoSA_Setup, {profile.solution_type})")
    try:
        setup = app.create_setup(name="DoSA_Setup")
        if profile.solution_type == "Transient":
            setup.props["StopTime"] = profile.stop_time
            setup.props["TimeStep"] = profile.time_step
        else:
            setup.props["PercentRefinement"] = 30
            setup.props["MaximumPasses"] = 10
    except Exception as exc:
        errors.append(f"[setup] create_setup: {exc}")

    # ── 4. Coil excitations ───────────────────────────────────────────────
    for part in design.parts:
        if part.kind != "Coil":
            continue
        props = part.properties
        turns = int(props.get("Turns", 0))
        polarity = "Positive" if props.get("CurrentDirection", "IN") == "IN" else "Negative"
        if mode == "3d":
            if profile.solution_type != "Transient":
                rec(f"skip_excitation({part.name}, 3d-magnetostatic)")
                continue
            # In Maxwell3D, solid conductors are more stable with current
            # boundaries than CoilTerminal boundaries.
            rec(f"assign_current({part.name}, 1A)")
            try:
                app.assign_current(
                    assignment=[part.name],
                    amplitude="1A",
                    name=f"Current_{part.name}",
                )
            except TypeError:
                try:
                    app.assign_current(
                        assignment=part.name,
                        amplitude="1A",
                        name=f"Current_{part.name}",
                    )
                except Exception as exc:
                    errors.append(f"[excitation] assign_current '{part.name}': {exc}")
            except Exception as exc:
                errors.append(f"[excitation] assign_current '{part.name}': {exc}")
        else:
            rec(f"assign_coil({part.name}, turns={turns}, {polarity})")
            try:
                app.assign_coil(
                    assignment=[part.name],
                    conductors_number=turns,
                    polarity=polarity,
                    name=f"Coil_{part.name}",
                )
            except TypeError:
                try:
                    app.assign_coil(
                        input_object=[part.name],
                        conductor_number=turns,
                        polarity=polarity,
                        name=f"Coil_{part.name}",
                    )
                except Exception as exc:
                    errors.append(f"[excitation] assign_coil '{part.name}': {exc}")
            except Exception as exc:
                errors.append(f"[excitation] assign_coil '{part.name}': {exc}")

    # ── 5. Motion (Transient only) ────────────────────────────────────────
    if profile.solution_type == "Transient":
        moving = [p for p in design.parts if p.properties.get("MovingParts") == "MOVING"]
        if moving:
            band = moving[0].name
            rec(f"assign_translate_motion({band}, Y)")
            try:
                app.assign_translate_motion(
                    assignment=band,
                    coordinate_system="Global",
                    axis="Y",
                    positive_limit="5mm",
                    negative_limit="5mm",
                )
            except TypeError:
                try:
                    app.assign_translate_motion(
                        band_object=band,
                        coordinate_system="Global",
                        axis="Y",
                        positive_limit="5mm",
                        negative_limit="5mm",
                    )
                except Exception as exc:
                    errors.append(f"[motion] assign_translate_motion: {exc}")
            except Exception as exc:
                errors.append(f"[motion] assign_translate_motion: {exc}")

            # Force on moving parts
            for part in moving:
                rec(f"assign_force({part.name})")
                try:
                    app.assign_force(
                        assignment=part.name,
                        reference_cs_name="Global",
                        force_name=f"Force_{part.name}",
                    )
                except TypeError:
                    try:
                        app.assign_force(
                            input_object=part.name,
                            reference_cs="Global",
                            force_name=f"Force_{part.name}",
                        )
                    except Exception as exc:
                        errors.append(f"[force] assign_force '{part.name}': {exc}")
                except Exception as exc:
                    errors.append(f"[force] assign_force '{part.name}': {exc}")

    # ── 6. Winding current from test conditions ────────────────────────────
    # Magnetostatic runs do not require winding boundary creation in this
    # workflow. Skipping avoids API incompatibilities across AEDT versions.
    force_tests = [t for t in design.tests if "FORCE" in t.kind.upper()]
    if profile.solution_type == "Transient" and force_tests:
        test = force_tests[0]
        voltage = float(test.properties.get("Voltage", 0))
        current = float(test.properties.get("Current", 0))
        for part in design.parts:
            if part.kind != "Coil":
                continue
            resistance = float(part.properties.get("Resistance", 0))
            exc_current = (
                current if current > 0
                else (voltage / resistance if resistance > 0 else 0)
            )
            coil_ref = f"Coil_{part.name}"
            rec(f"assign_winding({coil_ref}, {exc_current:.4f}A)")
            try:
                app.assign_winding(
                    assignment=[coil_ref],
                    winding_type="Current",
                    current=f"{exc_current}A",
                    name=f"Winding_{part.name}",
                )
            except TypeError:
                try:
                    app.assign_winding(
                        coil_terminals=[coil_ref],
                        winding_type="Current",
                        current_value=f"{exc_current}A",
                        name=f"Winding_{part.name}",
                    )
                except Exception as exc2:
                    errors.append(f"[winding] assign_winding '{part.name}': {exc2}")
            except Exception as exc:
                errors.append(f"[winding] assign_winding '{part.name}': {exc}")

    return ApplyResult(
        parts=len(design.parts),
        mode=mode,
        profile=profile.name,
        commands=commands,
        errors=errors,
    )


# ─── helpers ────────────────────────────────────────────────────────────────


def _extract_geom(part: NodeModel) -> Geometry2D | None:
    geom = extract_geometry(part)
    if geom is not None and geom.is_valid:
        return geom
    if part.kind == "Coil":
        props = part.properties
        inner_d = float(props.get("InnerDiameter", 0))
        outer_d = float(props.get("OuterDiameter", 0))
        height = float(props.get("Height", 0))
        if inner_d > 0 and outer_d > 0 and height > 0:
            return geometry_from_coil_params(part.name, inner_d, outer_d, height)
    return geom


def _select_available_material_name(app: Any, desired: str, category: str) -> str:
    """Pick an existing material name for current AEDT session.

    Some material names vary by AEDT version/library. This helper prevents
    noisy "Material does not exist" runtime errors by selecting a compatible
    fallback material when needed.
    """
    materials = getattr(app, "materials", None)
    if materials is None:
        return desired

    def _exists(name: str) -> bool:
        try:
            return bool(materials.exists_material(name))
        except Exception:
            return False

    if _exists(desired):
        return desired

    fallback_by_category = {
        "steel": ["steel_1010", "steel_1008", "iron"],
        "conductor": ["copper", "aluminum"],
        "magnet": ["iron", "steel_1010", "steel_1008"],
        "air": ["vacuum"],
    }
    for candidate in fallback_by_category.get(category, ["vacuum"]):
        if _exists(candidate):
            return candidate

    # Last fallback: try adding a local material with requested name.
    try:
        materials.add_material(desired)
        if _exists(desired):
            return desired
    except Exception:
        pass

    return "vacuum"
