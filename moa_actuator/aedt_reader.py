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
    """Internal: extract lightweight data from a Maxwell instance.

    Strategy:
    - Geometry objects → parts (with material-based classification)
    - Excitation info → merged into Coil parts as Current/Turns properties
    - Auto-generate DoSA-compatible ForceTest from excitation data
    - Skip heavy setup/mesh data — keep it portable across solvers
    """
    parts: list[NodeModel] = []
    tests: list[TestModel] = []

    # --- Extract geometry objects as parts ---
    try:
        for obj in m.modeler.object_list:
            props = _extract_object_properties(obj)
            kind = _classify_part(obj)
            parts.append(NodeModel(kind=kind, name=obj.name, properties=props))
    except Exception as e:
        parts.append(NodeModel(
            kind="Error", name="geometry_error",
            properties={"error": str(e)}
        ))

    # --- Extract excitations and merge into coil parts ---
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

                # Try to attach excitation data to matching coil part
                _attach_excitation_to_coil(parts, exc_name, exc_type, exc_props)
    except Exception:
        pass

    # --- Auto-generate DoSA-compatible tests from excitations ---
    total_current = _compute_total_current(excitation_summary)
    if total_current > 0:
        tests.append(TestModel(
            name="ForceTest_01",
            kind="ForceTest",
            properties={
                "Current": total_current,
                "Stroke": 0.0,
            },
        ))
        # Also add a basic stroke test
        tests.append(TestModel(
            name="StrokeTest_01",
            kind="StrokeTest",
            properties={
                "Current": total_current,
                "StrokeStart": 0.0,
                "StrokeEnd": 5.0,
                "StrokeStep": 1.0,
            },
        ))
    else:
        # Fallback: create empty force test
        tests.append(TestModel(
            name="ForceTest_01",
            kind="ForceTest",
            properties={"Current": 1000.0, "Stroke": 0.0},
        ))

    # --- Build project info (lightweight) ---
    project_props: dict[str, Any] = {
        "project_name": getattr(m, "project_name", ""),
        "design_name": getattr(m, "design_name", ""),
        "solution_type": getattr(m, "solution_type", ""),
        "design_type": getattr(m, "design_type", ""),
        "model_units": getattr(m.modeler, "model_units", "mm") if hasattr(m, "modeler") else "mm",
        "aedt_version": getattr(m, "aedt_version_id", ""),
    }

    return DesignModel(
        name=getattr(m, "project_name", file_path.stem),
        source_file=str(file_path),
        source_type="aedt_3d" if is_3d else "aedt_2d",
        parts=parts,
        tests=tests,
        nodes=[NodeModel(kind="ProjectInfo", name="AEDT Project", properties=project_props)],
    )


def _attach_excitation_to_coil(
    parts: list[NodeModel], exc_name: str, exc_type: str, exc_props: dict
):
    """Merge excitation data (current, turns) into the matching coil part."""
    # Extract current value from excitation properties
    current_val = (
        exc_props.get("Current", "")
        or exc_props.get("Value", "")
        or exc_props.get("CurrentValue", "")
    )
    turns = exc_props.get("NumTurns", "") or exc_props.get("Turns", "")

    # Find matching coil part by name similarity
    for part in parts:
        if part.kind != "Coil":
            continue
        # Match by name: excitation often references the object name
        obj_refs = exc_props.get("Objects", []) or exc_props.get("Object", "")
        if isinstance(obj_refs, str):
            obj_refs = [obj_refs]

        if part.name in obj_refs or part.name.lower() in exc_name.lower():
            if current_val:
                part.properties["Current"] = str(current_val)
            if turns:
                part.properties["Turns"] = str(turns)
            part.properties["ExcitationType"] = exc_type
            part.properties["ExcitationName"] = exc_name
            return

    # If no matching coil found, attach to first coil
    for part in parts:
        if part.kind == "Coil":
            if current_val:
                part.properties["Current"] = str(current_val)
            if turns:
                part.properties["Turns"] = str(turns)
            part.properties["ExcitationType"] = exc_type
            part.properties["ExcitationName"] = exc_name
            return


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
        # Parse numeric value (strip units like "A", "mA")
        try:
            numeric = "".join(c for c in current_str if c.isdigit() or c in ".-")
            if numeric:
                current = abs(float(numeric))
                turns = 1
                turns_str = str(props.get("NumTurns", "1") or "1")
                try:
                    turns = int("".join(c for c in turns_str if c.isdigit()) or "1")
                except ValueError:
                    turns = 1
                total += current * turns
        except (ValueError, TypeError):
            pass
    return total


def _extract_object_properties(obj) -> dict[str, Any]:
    """Extract lightweight properties from a modeler object.

    Keeps only what's needed for GUI display and solver re-run:
    Material, bounding-box derived geometry, solve_inside flag.
    """
    props: dict[str, Any] = {}

    props["Material"] = getattr(obj, "material_name", "vacuum")
    props["SolveInside"] = getattr(obj, "solve_inside", None)

    # Bounding box → derive rectangular ShapePoints for 2D cross-section display
    try:
        bb = obj.bounding_box
        if bb and len(bb) >= 6:
            # 3D bounding box: [xmin, ymin, zmin, xmax, ymax, zmax]
            # For 2D axisymmetric (RZ): R=x, Z=z
            xmin, ymin, zmin, xmax, ymax, zmax = bb[:6]
            props["BoundingBox"] = bb
            # Store as ShapePoints for geometry panel (RZ cross-section)
            props["ShapePoints"] = [
                {"x": xmin, "y": zmin},
                {"x": xmax, "y": zmin},
                {"x": xmax, "y": zmax},
                {"x": xmin, "y": zmax},
            ]
        elif bb and len(bb) >= 4:
            # 2D bounding box: [xmin, ymin, xmax, ymax]
            xmin, ymin, xmax, ymax = bb[:4]
            props["BoundingBox"] = bb
            props["ShapePoints"] = [
                {"x": xmin, "y": ymin},
                {"x": xmax, "y": ymin},
                {"x": xmax, "y": ymax},
                {"x": xmin, "y": ymax},
            ]
    except Exception:
        pass

    return props


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
