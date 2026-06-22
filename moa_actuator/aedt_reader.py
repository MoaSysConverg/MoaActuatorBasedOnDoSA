"""AEDT file reader — opens Maxwell 2D/3D projects and extracts design info.

Converts AEDT project data into DesignModel for display in the GUI.
Requires pyaedt (ansys.aedt.core) and a running or launchable AEDT instance.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import DesignModel, NodeModel, TestModel


def read_aedt_file(
    file_path: str | Path,
    *,
    aedt_version: str = "2026.1",
    non_graphical: bool = False,
    new_desktop: bool = False,
    design_name: str | None = None,
) -> DesignModel:
    """Open an AEDT file and extract geometry/materials/excitations into DesignModel.

    Parameters
    ----------
    file_path : path to .aedt file
    aedt_version : AEDT version string
    non_graphical : run without GUI
    new_desktop : launch a new desktop session
    design_name : specific design to open (None = active design)

    Returns
    -------
    DesignModel populated with parts (geometry objects) and tests (setups)
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"AEDT file not found: {file_path}")

    from ansys.aedt.core import Maxwell2d, Maxwell3d

    # Detect 2D vs 3D from design type (try 2D first, fallback to 3D)
    m = None
    is_3d = False
    try:
        m = Maxwell2d(
            project=str(file_path),
            version=aedt_version,
            non_graphical=non_graphical,
            new_desktop=new_desktop,
            design=design_name,
        )
        if "3D" in (m.design_type or ""):
            m.release_desktop(close_projects=False, close_desktop=False)
            m = Maxwell3d(
                project=str(file_path),
                version=aedt_version,
                non_graphical=non_graphical,
                new_desktop=new_desktop,
                design=design_name,
            )
            is_3d = True
    except Exception:
        # If 2D fails, try 3D directly
        if m is not None:
            try:
                m.release_desktop(close_projects=False, close_desktop=False)
            except Exception:
                pass
        m = Maxwell3d(
            project=str(file_path),
            version=aedt_version,
            non_graphical=non_graphical,
            new_desktop=new_desktop,
            design=design_name,
        )
        is_3d = True

    try:
        design = _extract_design(m, file_path, is_3d)
    finally:
        # Don't close the project — user may want to continue working
        try:
            m.release_desktop(close_projects=False, close_desktop=False)
        except Exception:
            pass

    return design


def read_aedt_from_instance(m) -> DesignModel:
    """Extract DesignModel from an already-open Maxwell2d/Maxwell3d instance.

    Parameters
    ----------
    m : Maxwell2d or Maxwell3d instance (already connected)

    Returns
    -------
    DesignModel
    """
    is_3d = "3D" in (getattr(m, "design_type", "") or "")
    file_path = Path(getattr(m, "project_path", "") or "unknown.aedt")
    return _extract_design(m, file_path, is_3d)


def _extract_design(m, file_path: Path, is_3d: bool) -> DesignModel:
    """Internal: extract data from Maxwell and convert to DoSA-compatible format.

    Strategy:
    - Geometry objects → parts with DoSA-style properties
      (KindKey, MovingParts, Material, NodeName, ShapePoints)
    - Excitation info → merged into Coil parts (Current, Turns, CurrentDirection)
    - Auto-generate DoSA-compatible tests (ForceTest, StrokeTest, CurrentTest)
    - Skip Region objects (vacuum/air) — DoSA doesn't list them as parts
    """
    parts: list[NodeModel] = []
    tests: list[TestModel] = []

    # --- Extract geometry objects as DoSA-format parts ---
    try:
        for obj in m.modeler.object_list:
            kind = _classify_part(obj)
            if kind == "Region":
                continue  # DoSA doesn't include Region as a part

            dosa_kind_key = _kind_to_kindkey(kind)
            mat_name = getattr(obj, "material_name", "vacuum") or "vacuum"

            # Build DoSA-style properties
            props: dict[str, Any] = {
                "NodeName": obj.name,
                "KindKey": dosa_kind_key,
                "MovingParts": "FIXED",
                "Material": _maxwell_mat_to_dosa_name(mat_name),
            }

            # Extract actual vertex geometry → Shape child node
            shape_child = _extract_shape_node(obj, is_3d)
            children: list[NodeModel] = []
            if shape_child is not None:
                children.append(shape_child)

            parts.append(NodeModel(
                kind=kind, name=obj.name,
                properties=props, children=children,
            ))
    except Exception as e:
        parts.append(NodeModel(
            kind="Error", name="geometry_error",
            properties={"error": str(e)}
        ))

    # --- Extract excitations and merge into coil parts (DoSA style) ---
    excitation_summary: dict[str, dict] = {}
    try:
        for exc_name in m.excitations:
            if exc_name in m.boundaries:
                bdry = m.boundaries[exc_name]
                exc_props = dict(bdry.props) if hasattr(bdry, "props") else {}
                exc_type = getattr(bdry, "type", "")
                excitation_summary[exc_name] = {
                    "type": exc_type,
                    "props": exc_props,
                }
                _attach_excitation_to_coil(parts, exc_name, exc_type, exc_props)
    except Exception:
        pass

    # --- Detect MOVING parts from Force boundaries ---
    try:
        for bdry_name, bdry in m.boundaries.items():
            bdry_type = getattr(bdry, "type", "")
            if "force" in bdry_type.lower():
                bdry_props = dict(bdry.props) if hasattr(bdry, "props") else {}
                obj_refs = bdry_props.get("Objects", []) or bdry_props.get("Object", "")
                if isinstance(obj_refs, str):
                    obj_refs = [obj_refs]
                for part in parts:
                    if part.name in obj_refs:
                        part.properties["MovingParts"] = "MOVING"
    except Exception:
        pass

    # --- Auto-generate DoSA-compatible tests ---
    total_current = _compute_total_current(excitation_summary)
    if total_current <= 0:
        total_current = 1000.0  # fallback

    # Estimate voltage/current from excitation (simplified)
    coil_current, _ = _get_coil_current_turns(parts)
    if coil_current <= 0:
        coil_current = total_current

    tests.append(TestModel(
        name="force",
        kind="ForceTest",
        properties={
            "NodeName": "force",
            "KindKey": "FORCE_TEST",
            "MeshSizePercent": 2,
            "Voltage": 0.0,
            "Current": coil_current,
            "MovingStroke": 0,
        },
    ))
    tests.append(TestModel(
        name="stroke",
        kind="StrokeTest",
        properties={
            "NodeName": "stroke",
            "KindKey": "STROKE_TEST",
            "MeshSizePercent": 2,
            "Voltage": 0.0,
            "Current": coil_current,
            "InitialStroke": 0,
            "FinalStroke": 5,
            "StepCount": 5,
        },
    ))
    tests.append(TestModel(
        name="current",
        kind="CurrentTest",
        properties={
            "NodeName": "current",
            "KindKey": "CURRENT_TEST",
            "MeshSizePercent": 2,
            "InitialCurrent": 0,
            "FinalCurrent": round(coil_current * 1.5, 5),
            "StepCount": 5,
            "MovingStroke": 0,
        },
    ))

    # --- Build project info ---
    project_props: dict[str, Any] = {
        "project_name": getattr(m, "project_name", ""),
        "design_name": getattr(m, "design_name", ""),
        "solution_type": getattr(m, "solution_type", ""),
        "design_type": getattr(m, "design_type", ""),
        "model_units": getattr(
            m.modeler, "model_units", "mm"
        ) if hasattr(m, "modeler") else "mm",
        "aedt_version": getattr(m, "aedt_version_id", ""),
    }

    return DesignModel(
        name=getattr(m, "project_name", file_path.stem),
        source_file=str(file_path),
        source_type="aedt_3d" if is_3d else "aedt_2d",
        parts=parts,
        tests=tests,
        nodes=[NodeModel(
            kind="ProjectInfo", name="AEDT Project",
            properties=project_props,
        )],
    )


def _attach_excitation_to_coil(
    parts: list[NodeModel], exc_name: str, exc_type: str, exc_props: dict
):
    """Merge excitation data into the matching coil part using DoSA keys."""
    current_val = (
        exc_props.get("Current", "")
        or exc_props.get("Value", "")
        or exc_props.get("CurrentValue", "")
    )
    turns = exc_props.get("NumTurns", "") or exc_props.get("Turns", "")

    # Parse numeric current value
    current_num = _parse_numeric(str(current_val)) if current_val else 0.0
    turns_num = int(_parse_numeric(str(turns))) if turns else 0

    # Determine current direction
    direction = "IN"
    if current_num < 0:
        direction = "OUT"
        current_num = abs(current_num)

    # Find matching coil part by name
    target = None
    for part in parts:
        if part.kind != "Coil":
            continue
        obj_refs = exc_props.get("Objects", []) or exc_props.get("Object", "")
        if isinstance(obj_refs, str):
            obj_refs = [obj_refs]
        if part.name in obj_refs or part.name.lower() in exc_name.lower():
            target = part
            break

    # Fallback to first coil
    if target is None:
        for part in parts:
            if part.kind == "Coil":
                target = part
                break

    if target is not None:
        if current_num > 0:
            target.properties["Current"] = current_num
        if turns_num > 0:
            target.properties["Turns"] = turns_num
        target.properties["CurrentDirection"] = direction


def _compute_total_current(excitation_summary: dict) -> float:
    """Compute total Amp-Turns from excitation data for test generation."""
    total = 0.0
    for exc_name, exc_info in excitation_summary.items():
        props = exc_info.get("props", {})
        current_str = str(
            props.get("Current", "")
            or props.get("Value", "")
            or props.get("CurrentValue", "")
            or "0"
        )
        current = _parse_numeric(current_str)
        turns_str = str(props.get("NumTurns", "1") or "1")
        turns = max(1, int(_parse_numeric(turns_str) or 1))
        total += abs(current) * turns
    return total


def _parse_numeric(s: str) -> float:
    """Extract a numeric value from a string that may contain units."""
    numeric = "".join(c for c in s if c.isdigit() or c in ".-")
    try:
        return float(numeric) if numeric else 0.0
    except (ValueError, TypeError):
        return 0.0


def _get_coil_current_turns(parts: list[NodeModel]) -> tuple[float, int]:
    """Get current and turns from the first coil part."""
    for part in parts:
        if part.kind == "Coil":
            current = float(part.properties.get("Current", 0) or 0)
            turns = int(part.properties.get("Turns", 1) or 1)
            return current, turns
    return 0.0, 1


def _kind_to_kindkey(kind: str) -> str:
    """Convert GUI kind to DoSA KindKey."""
    mapping = {
        "Coil": "COIL",
        "Magnet": "MAGNET",
        "Steel": "STEEL",
        "Non-Kind": "NON_KIND",
        "Other": "NON_KIND",
    }
    return mapping.get(kind, "NON_KIND")


# Reverse mapping: Maxwell material name → DoSA display name
_MAXWELL_TO_DOSA_MAT: dict[str, str] = {
    "copper": "Copper",
    "aluminum": "Aluminum",
    "steel_1010": "1010 Steel",
    "steel_1020": "1020 Steel",
    "steel_1008": "1008 Steel",
    "iron": "Pure Iron",
    "stainless_steel": "430 Stainless Steel",
    "m19_29g": "M-19",
    "ndfeb": "NdFeB",
    "vacuum": "Air",
}


def _maxwell_mat_to_dosa_name(maxwell_name: str) -> str:
    """Convert Maxwell material name to DoSA-style display name."""
    key = maxwell_name.lower().strip()
    if key in _MAXWELL_TO_DOSA_MAT:
        return _MAXWELL_TO_DOSA_MAT[key]
    # Return original if no mapping found (capitalize nicely)
    return maxwell_name.replace("_", " ").title() if maxwell_name else "Air"


def _extract_shape_node(obj, is_3d: bool) -> NodeModel | None:
    """Extract vertex polygon from a modeler object as a DoSA Shape node.

    For 2D: reads obj.vertices directly (XY or RZ polygon).
    For 3D: projects vertices onto the RZ plane using bounding box.
    Returns a NodeModel(kind="Shape") with raw_lines containing
    PointX/PointY pairs, compatible with extract_geometry().
    """
    try:
        verts = obj.vertices
        if not verts:
            return _shape_from_bounding_box(obj, is_3d)

        # Collect vertex positions
        positions = []
        for v in verts:
            pos = v.position if hasattr(v, "position") else v
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                positions.append(pos)

        if len(positions) < 3:
            return _shape_from_bounding_box(obj, is_3d)

        # 2D Maxwell uses ZX plane: position = (R, 0, Z)
        # 3D Maxwell: project to RZ plane
        # In both cases, use (x, z) as the 2D cross-section
        pts = [(p[0], p[2]) for p in positions
               if len(p) >= 3]
        if not pts:
            pts = [(p[0], p[1]) for p in positions]

        # Remove duplicates while preserving order
        seen = set()
        unique_pts = []
        for p in pts:
            key = (round(p[0], 6), round(p[1], 6))
            if key not in seen:
                seen.add(key)
                unique_pts.append(p)
        pts = unique_pts

        if len(pts) < 3:
            return _shape_from_bounding_box(obj, is_3d)

        # Build raw_lines in DoSA format
        raw_lines = [
            f"BasePointX={pts[0][0]}",
            f"BasePointY={pts[0][1]}",
            "FaceType=POLYGON",
        ]
        for x, y in pts:
            raw_lines.append(f"PointX={x}")
            raw_lines.append(f"PointY={y}")

        return NodeModel(
            kind="Shape", name="Shape",
            properties={
                "BasePointX": pts[0][0],
                "BasePointY": pts[0][1],
                "FaceType": "POLYGON",
            },
            raw_lines=raw_lines,
        )
    except Exception:
        return _shape_from_bounding_box(obj, is_3d)


def _shape_from_bounding_box(obj, is_3d: bool) -> NodeModel | None:
    """Fallback: create Shape node from bounding box."""
    try:
        bb = obj.bounding_box
        if not bb:
            return None
        # Always use X and Z for cross-section (2D ZX plane)
        if len(bb) >= 6:
            xmin, _, zmin, xmax, _, zmax = bb[:6]
            pts = [(xmin, zmin), (xmax, zmin),
                   (xmax, zmax), (xmin, zmax)]
        elif len(bb) >= 4:
            xmin, ymin, xmax, ymax = bb[:4]
            pts = [(xmin, ymin), (xmax, ymin),
                   (xmax, ymax), (xmin, ymax)]
        else:
            return None

        raw_lines = [
            f"BasePointX={pts[0][0]}",
            f"BasePointY={pts[0][1]}",
            "FaceType=POLYGON",
        ]
        for x, y in pts:
            raw_lines.append(f"PointX={x}")
            raw_lines.append(f"PointY={y}")

        return NodeModel(
            kind="Shape", name="Shape",
            properties={
                "BasePointX": pts[0][0],
                "BasePointY": pts[0][1],
                "FaceType": "POLYGON",
            },
            raw_lines=raw_lines,
        )
    except Exception:
        return None


def _order_polygon(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Order 2D points into a proper polygon by angle from centroid."""
    import math
    if len(pts) <= 3:
        return pts
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return sorted(pts, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))


def _classify_part(obj) -> str:
    """Classify a modeler object into Coil/Magnet/Steel/Other based on material."""
    mat = (getattr(obj, "material_name", "") or "").lower()

    # Conductors → Coil
    if any(c in mat for c in ["copper", "aluminum", "conductor"]):
        return "Coil"

    # Magnets
    if any(m in mat for m in ["n35", "n38", "n40", "n42", "n45", "n48", "n50", "n52",
                               "smco", "alnico", "ceramic", "ndfeb", "magnet"]):
        return "Magnet"

    # Steels / Ferromagnetic
    if any(s in mat for s in ["steel", "iron", "sus", "nickel", "cobalt", "ferrite",
                               "hiperco", "m-19", "m-27", "m-36", "m-43", "m-45"]):
        return "Steel"

    # Vacuum/Air → region or non-kind
    if mat in ("vacuum", "air", ""):
        return "Region"

    return "Other"
