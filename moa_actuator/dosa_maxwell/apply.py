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
    # Determine the required model plane from solution type
    # Z-axis solutions (MagnetostaticZ, TransientZ) → RZ plane: [R, 0, Z]
    # XY solutions (MagnetostaticXY, TransientXY) → XY plane: [X, Y, 0]
    need_zx_plane = _detect_about_z(app)
    if need_zx_plane:
        rec("plane_check: about-Z detected → geometry will be placed on ZX plane")

    for part in design.parts:
        geom = _extract_geom(part)
        if geom is None or not geom.is_valid:
            errors.append(f"[geometry] No valid shape for '{part.name}'")
            continue

        pts = geom.to_polyline_points()

        # Plane check: ensure geometry is on the correct plane
        if need_zx_plane:
            pts = _ensure_zx_plane(pts)
            rec(f"modeler.create_polyline({part.name}, {len(pts)} pts, ZX plane)")
        else:
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

    # ── 2b. Region & boundary condition ──────────────────────────────────
    try:
        region = app.modeler.create_region(pad_percent=100)
        region.material_name = "vacuum"
        rec("create_region(pad_percent=100, material=vacuum)")
        try:
            app.assign_vector_potential(
                assignment=region.edges,
                boundary="VectorPotential1",
            )
            rec("assign_vector_potential(region.edges, VectorPotential1)")
        except Exception as exc:
            errors.append(f"[boundary] assign_vector_potential: {exc}")
    except Exception as exc:
        errors.append(f"[region] create_region: {exc}")

    # ── 3. Setup (must exist before motion) ──────────────────────────────
    rec(f"create_setup(DoSA_Setup, {profile.solution_type})")
    try:
        setup = app.create_setup(name="DoSA_Setup")
        if profile.solution_type == "Transient":
            setup.props["StopTime"] = profile.stop_time
            setup.props["TimeStep"] = profile.time_step
        else:
            setup.props["MaximumPasses"] = 3
            setup.props["MinimumPasses"] = 1
            setup.props["PercentRefinement"] = 30
            setup.props["PercentError"] = 0.1
            setup.props["RelativeResidual"] = 1e-6
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
            if profile.solution_type == "Transient":
                # Transient 2D: assign_coil creates the terminal referenced
                # by assign_winding in Section 6.
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
            else:
                # Magnetostatic 2D: assign_current (AT) in Section 6 handles
                # excitation directly — no coil terminal needed.
                rec(f"skip_assign_coil({part.name}, magnetostatic-2d → assign_current in sec6)")

    # ── 5. Force & Motion ────────────────────────────────────────────────
    # Assign force on all MOVING parts (Magnetostatic & Transient).
    # Assign motion only for Transient.
    moving = [p for p in design.parts if p.properties.get("MovingParts") == "MOVING"]

    # Design variable for plunger position (used in parametric sweep)
    if moving:
        try:
            app["move"] = "0mm"
            rec("variable: move = 0mm")
        except Exception as exc:
            errors.append(f"[variable] move: {exc}")

    for part in moving:
        rec(f"assign_force({part.name})")
        try:
            app.assign_force(
                assignment=part.name,
                force_name=f"Force_{part.name}",
            )
        except TypeError:
            try:
                app.assign_force(
                    input_object=part.name,
                    force_name=f"Force_{part.name}",
                )
            except Exception as exc:
                errors.append(f"[force] assign_force '{part.name}': {exc}")
        except Exception as exc:
            errors.append(f"[force] assign_force '{part.name}': {exc}")

    if profile.solution_type == "Transient" and moving:
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

    # ── 6. Winding current from test conditions ────────────────────────────
    # Apply excitation current to coils.  For Magnetostatic (no winding),
    # use assign_current directly.  For Transient, create winding + current.
    force_tests = [t for t in design.tests if "FORCE" in t.kind.upper()]
    if force_tests:
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
            if exc_current <= 0:
                continue

            if profile.solution_type == "Transient":
                # Transient: winding 생성 후 전류 인가
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
            else:
                # Magnetostatic: assign_current directly (no winding needed)
                # Homogenized coil: Maxwell expects total ampere-turns (AT)
                turns = int(part.properties.get("Turns", 1))
                total_at = exc_current * turns
                var_name = f"Amp_{part.name}"
                rec(f"assign_current({part.name}, {total_at:.4f}A [{exc_current:.5f}A x {turns}T])")
                try:
                    app[var_name] = f"{total_at}A"
                    app.assign_current(
                        assignment=[part.name],
                        amplitude=var_name,
                        name=f"Current_{part.name}",
                    )
                except TypeError:
                    try:
                        app.assign_current(
                            assignment=part.name,
                            amplitude=f"{total_at}A",
                            name=f"Current_{part.name}",
                        )
                    except Exception as exc2:
                        errors.append(f"[current] assign_current '{part.name}': {exc2}")
                except Exception as exc:
                    errors.append(f"[current] assign_current '{part.name}': {exc}")

    # ── 7. Parametric sweep (StrokeTest) ──────────────────────────────────
    # If a StrokeTest exists, create a parametric sweep over Amp and move.
    stroke_tests = [t for t in design.tests if "STROKE" in t.kind.upper()]
    if stroke_tests and moving and profile.solution_type != "Transient":
        st = stroke_tests[0]
        stroke_start = float(st.properties.get("InitialStroke", 0))
        stroke_end = float(st.properties.get("FinalStroke", 4))
        step_count = int(st.properties.get("StepCount", 5))
        stroke_step = (stroke_end - stroke_start) / max(step_count, 1)
        # Amp sweep: use force test current as center, build range
        coil_parts = [p for p in design.parts if p.kind == "Coil"]
        if coil_parts and force_tests:
            ft = force_tests[0]
            ft_current = float(ft.properties.get("Current", 0))
            ft_voltage = float(ft.properties.get("Voltage", 0))
            ft_resistance = float(coil_parts[0].properties.get("Resistance", 0))
            base_current = (
                ft_current if ft_current > 0
                else (ft_voltage / ft_resistance if ft_resistance > 0 else 1)
            )
            coil_turns = int(coil_parts[0].properties.get("Turns", 1))
            base_at = base_current * coil_turns
            # Build sweep: 25%, 50%, 75%, 100%, 125% of base AT
            amp_start = round(base_at * 0.25, 1)
            amp_end = round(base_at * 1.25, 1)
            amp_step = round(base_at * 0.25, 1)
            amp_var = f"Amp_{coil_parts[0].name}"

            rec(f"parametric_sweep({amp_var}: {amp_start}~{amp_end}, "
                f"move: {stroke_start}~{stroke_end})")
            try:
                sweep = app.parametrics.add(
                    amp_var, amp_start, amp_end, amp_step,
                    name="ParametricSetup1",
                    variation_type="LinearStep",
                )
                sweep.add_variation(
                    "move", stroke_start, stroke_end, stroke_step,
                    variation_type="LinearStep",
                )
                rec("parametric_sweep created: ParametricSetup1")
            except Exception as exc:
                errors.append(f"[parametric] sweep: {exc}")

    # ── 8. Report ─────────────────────────────────────────────────────────
    # Create Force report for MOVING parts.
    if moving:
        force_expr = f"Force_{moving[0].name}.Force_z"
        coil_parts = [p for p in design.parts if p.kind == "Coil"]
        amp_var = f"Amp_{coil_parts[0].name}" if coil_parts else None

        if stroke_tests and amp_var:
            # Parametric sweep report: Amp × move variations
            rec(f"create_report(Force Plot, {force_expr}, Amp×move)")
            try:
                app.post.create_report(
                    expressions=[force_expr],
                    variations={amp_var: "All", "move": "All"},
                    plot_name="Force Plot 1",
                    primary_sweep_variable="move",
                    plot_type="Rectangular Plot",
                )
            except Exception as exc:
                errors.append(f"[report] create_report: {exc}")
        else:
            # Simple force report
            rec(f"create_report(Force Plot, {force_expr})")
            try:
                app.post.create_report(
                    expressions=[force_expr],
                    plot_name="Force Plot 1",
                    plot_type="Rectangular Plot",
                )
            except Exception as exc:
                errors.append(f"[report] create_report: {exc}")

    return ApplyResult(
        parts=len(design.parts),
        mode=mode,
        profile=profile.name,
        commands=commands,
        errors=errors,
    )


# ─── helpers ────────────────────────────────────────────────────────────────


def _detect_about_z(app: Any) -> bool:
    """Detect if the Maxwell 2D session is in 'about Z' (RZ axisymmetric) mode.

    pyAEDT strips the 'Z'/'XY' suffix from solution_type after creation,
    setting geometry_mode internally.  So we check multiple sources:

    1. solution_type string ending with 'Z' (before setter strips it)
    2. design_solutions.xy_plane == False → "about Z" mode
    3. design_solutions.geometry_mode containing "Z"
    4. The odesign COM property (AEDT internal)
    """
    # Check 1: solution_type string (may still have suffix)
    sol = getattr(app, "solution_type", "") or ""
    if sol.endswith("Z") and not sol.endswith("XY"):
        return True

    # Check 2: design_solutions.xy_plane (most reliable after creation)
    try:
        ds = getattr(app, "design_solutions", None)
        if ds is not None:
            xy_plane = getattr(ds, "xy_plane", None)
            if xy_plane is False:
                return True
            # Also check geometry_mode string
            geo_mode = getattr(ds, "geometry_mode", "") or ""
            if "z" in geo_mode.lower() or "rz" in geo_mode.lower():
                return True
    except Exception:
        pass

    # Check 3: AEDT COM/gRPC property
    try:
        odesign = getattr(app, "odesign", None)
        if odesign is not None:
            sol_info = odesign.GetSolutionType()
            if isinstance(sol_info, (list, tuple)) and len(sol_info) >= 2:
                # Second element is geometry mode: "XY" or "about Z"
                if "z" in str(sol_info[1]).lower():
                    return True
            elif isinstance(sol_info, str) and sol_info.endswith("Z"):
                return True
    except Exception:
        pass

    return False


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


def _ensure_zx_plane(pts: list[list[float]]) -> list[list[float]]:
    """Ensure points lie on the ZX plane (Y=0) for RZ axisymmetric solutions.

    DoSA geometry is stored as (R, Z) which is typically exported as [X, Y, 0]
    (XY plane). For MagnetostaticZ/TransientZ, Maxwell 2D expects the geometry
    on the RZ plane: [R, 0, Z] where R=X and Z=Y_original.

    Detection logic:
    - If all Z=0 and some X,Y ≠ 0 → geometry is on XY plane → transform to ZX
    - If all Y=0 → already on ZX plane → no change
    - If on another plane → attempt best-effort transform

    Returns:
        Transformed points as [[R, 0, Z], ...]
    """
    if not pts:
        return pts

    # Check which plane the points are on
    all_z_zero = all(abs(p[2]) < 1e-6 for p in pts)
    all_y_zero = all(abs(p[1]) < 1e-6 for p in pts)
    all_x_zero = all(abs(p[0]) < 1e-6 for p in pts)

    if all_y_zero:
        # Already on ZX plane (X=R, Z=Z, Y=0) → correct for MagnetostaticZ
        return pts

    if all_z_zero:
        # Points on XY plane [X, Y, 0] → rotate to ZX plane [X, 0, Y]
        # In Maxwell 2D RZ: X=R (radial), Z=axial direction
        logger.info("Geometry on XY plane → transforming to ZX plane (R=X, Z=Y)")
        return [[p[0], 0.0, p[1]] for p in pts]

    if all_x_zero:
        # Points on YZ plane [0, Y, Z] → move to ZX plane [Y, 0, Z]
        logger.info("Geometry on YZ plane → transforming to ZX plane (R=Y, Z=Z)")
        return [[p[1], 0.0, p[2]] for p in pts]

    # Mixed plane or 3D points — project onto ZX by zeroing Y
    logger.warning("Geometry not on a standard plane — projecting onto ZX (Y=0)")
    return [[p[0], 0.0, p[2]] for p in pts]
