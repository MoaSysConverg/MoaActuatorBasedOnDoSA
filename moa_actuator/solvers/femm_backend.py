"""FEMM backend using pyfemm (2D axisymmetric magnetics).

Ports the DoSA-2D ScriptFemm.cs workflow to Python.
Supports ForceTest (current sweep) and StrokeTest (displacement sweep).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..geometry import Geometry2D, extract_geometry, geometry_from_coil_params
from ..mapping import resolve_material
from ..models import DesignModel, NodeModel
from .base import SolveResult, SolverBackend

logger = logging.getLogger(__name__)

MOVING_GROUP = 1


class FemmBackend(SolverBackend):
    """pyfemm-based 2D axisymmetric solver backend."""

    @property
    def name(self) -> str:
        return "femm"

    @property
    def supported_modes(self) -> list[str]:
        return ["2d"]

    def solve(
        self,
        design: DesignModel,
        mode: str = "2d",
        out_dir: str | None = None,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> SolveResult:
        if mode != "2d":
            return SolveResult(
                ok=False, mode=mode, solver="femm",
                errors=["FEMM backend only supports 2D axisymmetric mode"],
            )

        out_path = Path(out_dir) if out_dir else Path("./output/femm")
        out_path.mkdir(parents=True, exist_ok=True)

        commands: list[dict[str, Any]] = []
        errors: list[str] = []

        current = float(kwargs.get("current", 1000))
        stroke = float(kwargs.get("stroke", 0))
        mesh_size = float(kwargs.get("mesh_size", 1.0))

        if dry_run:
            return self._dry_run(design, out_path, current, stroke, mesh_size, commands)

        return self._live_run(design, out_path, current, stroke, mesh_size, commands, errors)

    def _dry_run(
        self, design: DesignModel, out_path: Path,
        current: float, stroke: float, mesh_size: float,
        commands: list[dict[str, Any]],
    ) -> SolveResult:
        """Generate command log without executing FEMM."""
        commands.append({"method": "openfemm", "args": {}})
        commands.append({"method": "newdocument", "args": {"doctype": 0}})
        commands.append({"method": "mi_probdef", "args": {"freq": 0, "units": "millimeters", "type": "axi"}})

        materials_used = set()
        for part in design.parts:
            mat_name = part.properties.get("Material", "Air")
            try:
                mat = resolve_material(mat_name)
                femm_mat = _to_femm_material(mat.maxwell_name)
                materials_used.add(femm_mat)
            except ValueError:
                materials_used.add("Air")

        for mat in materials_used:
            commands.append({"method": "mi_getmaterial", "args": {"name": mat}})

        for part in design.parts:
            geom = self._get_geometry(part)
            if geom and geom.is_valid:
                is_moving = part.properties.get("MovingParts", "") == "MOVING"
                commands.append({
                    "method": "draw_polygon",
                    "args": {"name": part.name, "points": len(geom.points), "group": MOVING_GROUP if is_moving else 0},
                })

        commands.append({"method": "mi_addcircprop", "args": {"name": "Coil", "current": current, "type": 1}})

        for part in design.parts:
            geom = self._get_geometry(part)
            if geom and geom.is_valid:
                commands.append({"method": "mi_setblockprop", "args": {"name": part.name}})

        commands.append({"method": "mi_addboundprop", "args": {"name": "BC", "type": 3}})

        if stroke != 0:
            commands.append({"method": "mi_movetranslate", "args": {"dx": 0, "dy": stroke}})

        commands.append({"method": "mi_analyze", "args": {}})
        commands.append({"method": "mi_loadsolution", "args": {}})
        commands.append({"method": "mo_blockintegral", "args": {"type": 19, "note": "Force_Y (stress tensor)"}})
        commands.append({"method": "closefemm", "args": {}})

        return SolveResult(ok=True, mode="2d", solver="femm", commands=commands, errors=[])

    def _live_run(
        self, design: DesignModel, out_path: Path,
        current: float, stroke: float, mesh_size: float,
        commands: list[dict[str, Any]], errors: list[str],
    ) -> SolveResult:
        """Execute FEMM simulation using pyfemm."""
        try:
            import femm
        except ImportError:
            return SolveResult(
                ok=False, mode="2d", solver="femm",
                errors=["pyfemm not installed. Install with: pip install pyfemm"],
            )

        force_data: list[dict[str, Any]] = []

        try:
            femm.openfemm()
            femm.newdocument(0)
            femm.mi_probdef(0, "millimeters", "axi")
            femm.mi_hidegrid()

            # Load materials
            femm.mi_getmaterial("Air")
            materials_map: dict[str, str] = {}
            for part in design.parts:
                mat_name = part.properties.get("Material", "Air")
                try:
                    mat = resolve_material(mat_name)
                    femm_mat = _to_femm_material(mat.maxwell_name)
                    if femm_mat not in materials_map.values():
                        femm.mi_getmaterial(femm_mat)
                    materials_map[part.name] = femm_mat
                except ValueError:
                    materials_map[part.name] = "Air"

            # Draw geometry
            for part in design.parts:
                geom = self._get_geometry(part)
                if geom is None or not geom.is_valid:
                    errors.append(f"[geometry] No valid shape for '{part.name}'")
                    continue
                is_moving = part.properties.get("MovingParts", "") == "MOVING"
                _draw_polygon(geom, MOVING_GROUP if is_moving else 0)

            # Circuit
            femm.mi_addcircprop("Coil", current, 1)

            # Block labels
            for part in design.parts:
                geom = self._get_geometry(part)
                if geom is None or not geom.is_valid:
                    continue
                cx, cy = _interior_point(geom)
                mat = materials_map.get(part.name, "Air")
                is_moving = part.properties.get("MovingParts", "") == "MOVING"
                group = MOVING_GROUP if is_moving else 0
                turns = int(part.properties.get("Turns", 0)) if part.kind == "Coil" else 0
                circuit = "Coil" if part.kind == "Coil" else ""

                femm.mi_addblocklabel(cx, cy)
                femm.mi_selectlabel(cx, cy)
                femm.mi_setblockprop(mat, 0, mesh_size, circuit, 0, group, turns)
                femm.mi_clearselected()

            # Boundary
            _draw_boundary(design)

            # Stroke
            if stroke != 0:
                femm.mi_seteditmode("group")
                femm.mi_selectgroup(MOVING_GROUP)
                femm.mi_movetranslate(0, stroke)

            # Save & solve
            fem_path = str(out_path / "model.fem")
            femm.mi_saveas(fem_path)
            femm.mi_analyze()
            femm.mi_loadsolution()

            # Extract force
            femm.mo_groupselectblock(MOVING_GROUP)
            force_y = femm.mo_blockintegral(19)
            femm.mo_clearblock()

            force_data.append({"current": current, "stroke": stroke, "Force_Y": force_y})

            femm.mo_close()
            femm.mi_close()
            femm.closefemm()

        except Exception as exc:
            errors.append(f"[femm] Execution error: {exc}")
            try:
                import femm
                femm.closefemm()
            except Exception:
                pass

        return SolveResult(
            ok=len(errors) == 0, mode="2d", solver="femm",
            commands=commands, errors=errors, force_data=force_data,
            project_path=str(out_path / "model.fem") if not errors else None,
        )

    def solve_sweep(
        self, design: DesignModel, out_dir: str | None = None,
        current_list: list[float] | None = None,
        stroke_list: list[float] | None = None,
        fixed_current: float = 1000, fixed_stroke: float = 0,
        mesh_size: float = 1.0,
    ) -> SolveResult:
        """Run parametric sweep (current or stroke) and return force data."""
        try:
            import femm
        except ImportError:
            return SolveResult(ok=False, mode="2d", solver="femm", errors=["pyfemm not installed"])

        out_path = Path(out_dir) if out_dir else Path("./output/femm")
        out_path.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []
        force_data: list[dict[str, Any]] = []

        try:
            femm.openfemm()
            femm.newdocument(0)
            femm.mi_probdef(0, "millimeters", "axi")
            femm.mi_hidegrid()
            self._setup_model(design, mesh_size, fixed_current)

            if current_list:
                if fixed_stroke != 0:
                    femm.mi_seteditmode("group")
                    femm.mi_selectgroup(MOVING_GROUP)
                    femm.mi_movetranslate(0, fixed_stroke)
                femm.mi_saveas(str(out_path / "model.fem"))

                for curr in current_list:
                    femm.mi_modifycircprop("Coil", 1, curr)
                    femm.mi_analyze()
                    femm.mi_loadsolution()
                    femm.mo_groupselectblock(MOVING_GROUP)
                    force_y = femm.mo_blockintegral(19)
                    femm.mo_clearblock()
                    force_data.append({"current": curr, "stroke": fixed_stroke, "Force_Y": force_y})

            elif stroke_list:
                femm.mi_saveas(str(out_path / "model.fem"))
                prev_stroke = 0.0
                for stk in stroke_list:
                    delta = stk - prev_stroke
                    if delta != 0:
                        femm.mi_seteditmode("group")
                        femm.mi_selectgroup(MOVING_GROUP)
                        femm.mi_movetranslate(0, delta)
                        prev_stroke = stk
                    femm.mi_analyze()
                    femm.mi_loadsolution()
                    femm.mo_groupselectblock(MOVING_GROUP)
                    force_y = femm.mo_blockintegral(19)
                    femm.mo_clearblock()
                    force_data.append({"current": fixed_current, "stroke": stk, "Force_Y": force_y})

            femm.mo_close()
            femm.mi_close()
            femm.closefemm()

        except Exception as exc:
            errors.append(f"[femm] Sweep error: {exc}")
            try:
                femm.closefemm()
            except Exception:
                pass

        return SolveResult(
            ok=len(errors) == 0, mode="2d", solver="femm",
            commands=[], errors=errors, force_data=force_data,
            project_path=str(out_path / "model.fem"),
        )

    def _setup_model(self, design: DesignModel, mesh_size: float, current: float):
        """Set up full FEMM model (materials, geometry, blocks, boundary)."""
        import femm

        femm.mi_getmaterial("Air")
        materials_map: dict[str, str] = {}
        for part in design.parts:
            mat_name = part.properties.get("Material", "Air")
            try:
                mat = resolve_material(mat_name)
                femm_mat = _to_femm_material(mat.maxwell_name)
                if femm_mat not in materials_map.values():
                    femm.mi_getmaterial(femm_mat)
                materials_map[part.name] = femm_mat
            except ValueError:
                materials_map[part.name] = "Air"

        for part in design.parts:
            geom = self._get_geometry(part)
            if geom is None or not geom.is_valid:
                continue
            is_moving = part.properties.get("MovingParts", "") == "MOVING"
            _draw_polygon(geom, MOVING_GROUP if is_moving else 0)

        femm.mi_addcircprop("Coil", current, 1)

        for part in design.parts:
            geom = self._get_geometry(part)
            if geom is None or not geom.is_valid:
                continue
            cx, cy = _interior_point(geom)
            mat = materials_map.get(part.name, "Air")
            is_moving = part.properties.get("MovingParts", "") == "MOVING"
            group = MOVING_GROUP if is_moving else 0
            turns = int(part.properties.get("Turns", 0)) if part.kind == "Coil" else 0
            circuit = "Coil" if part.kind == "Coil" else ""
            femm.mi_addblocklabel(cx, cy)
            femm.mi_selectlabel(cx, cy)
            femm.mi_setblockprop(mat, 0, mesh_size, circuit, 0, group, turns)
            femm.mi_clearselected()

        _draw_boundary(design)

    def _get_geometry(self, part: NodeModel) -> Geometry2D | None:
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
        return None


def _interior_point(geom: Geometry2D) -> tuple[float, float]:
    """Find a point guaranteed to be inside the polygon.

    For non-convex (L-shaped) parts, bounding box center may fall outside.
    Uses centroid of first triangle as a robust fallback.
    """
    pts = geom.points
    # Try centroid of first triangle (vertices 0, 1, 2)
    if len(pts) >= 3:
        cx = (pts[0].x + pts[1].x + pts[2].x) / 3
        cy = (pts[0].y + pts[1].y + pts[2].y) / 3
        return cx, cy
    # Fallback to bbox center
    return (geom.min_x + geom.max_x) / 2, (geom.min_y + geom.max_y) / 2


def _to_femm_material(maxwell_name: str) -> str:
    """Map Maxwell material names to FEMM library names."""
    _map = {
        "steel_1010": "1010 Steel",
        "steel_1020": "1020 Steel",
        "steel_1008": "1008 Steel",
        "iron": "Pure Iron",
        "stainless_steel": "430 Stainless Steel",
        "M19_29G": "M-19 Steel",
        "copper": "Copper",
        "aluminum": "Aluminum, 1100",
        "NdFe30": "NdFeB 30 MGOe",
        "NdFe35": "NdFeB 35 MGOe",
        "NdFe38": "NdFeB 38 MGOe",
        "NdFe40": "NdFeB 40 MGOe",
        "NdFe42": "NdFeB 42 MGOe",
        "NdFe45": "NdFeB 45 MGOe",
        "NdFe48": "NdFeB 48 MGOe",
        "NdFe50": "NdFeB 50 MGOe",
        "NdFe52": "NdFeB 52 MGOe",
        "vacuum": "Air",
    }
    return _map.get(maxwell_name, "Air")


def _draw_polygon(geom: Geometry2D, group: int = 0):
    """Draw a closed polygon in FEMM."""
    import femm

    points = geom.points
    if len(points) < 3:
        return

    for p in points:
        femm.mi_addnode(p.x, p.y)

    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)]
        femm.mi_addsegment(p1.x, p1.y, p2.x, p2.y)

    if group != 0:
        for p in points:
            femm.mi_selectnode(p.x, p.y)
        femm.mi_setgroup(group)
        femm.mi_clearselected()
        for i in range(len(points)):
            p1 = points[i]
            p2 = points[(i + 1) % len(points)]
            femm.mi_selectsegment((p1.x + p2.x) / 2, (p1.y + p2.y) / 2)
        femm.mi_setgroup(group)
        femm.mi_clearselected()


def _draw_boundary(design: DesignModel):
    """Draw boundary region around the design."""
    import femm

    all_geoms = []
    for part in design.parts:
        geom = extract_geometry(part)
        if geom and geom.is_valid:
            all_geoms.append(geom)
    if not all_geoms:
        return

    max_x = max(g.max_x for g in all_geoms)
    min_y = min(g.min_y for g in all_geoms)
    max_y = max(g.max_y for g in all_geoms)

    pad = max(max_x, max_y - min_y) * 0.75
    bx_max = max_x + pad
    by_min = min_y - pad
    by_max = max_y + pad

    femm.mi_addboundprop("BC", 0, 0, 0, 0, 0, 0, 0, 0, 3)

    corners = [(0, by_min), (bx_max, by_min), (bx_max, by_max), (0, by_max)]
    for cx, cy in corners:
        femm.mi_addnode(cx, cy)
    for i in range(4):
        x1, y1 = corners[i]
        x2, y2 = corners[(i + 1) % 4]
        femm.mi_addsegment(x1, y1, x2, y2)
        femm.mi_selectsegment((x1 + x2) / 2, (y1 + y2) / 2)
        femm.mi_setsegmentprop("BC", 0, 1, 0, 0)
        femm.mi_clearselected()

    air_x = bx_max * 0.8
    air_y = by_max - pad * 0.1
    femm.mi_addblocklabel(air_x, air_y)
    femm.mi_selectlabel(air_x, air_y)
    femm.mi_setblockprop("Air", 0, 2.0, "", 0, 0, 0)
    femm.mi_clearselected()
