"""GetDP backend wrapping DoSA-3D script generation logic.

Generates Define.geo, BH.pro, Design.geo, Design.pro from DoSA-3D
design data and STEP files, then executes Gmsh + GetDP via subprocess.

Faithfully replicates the DoSA-3D C# application's script generation:
- STEP file import with OpenCASCADE
- Outer/inner air region boxes with boolean operations
- Nonlinear B-H steel materials
- Coil circular current density (js0[])
- Magnet Hc/Br vectors
- Maxwell stress tensor force extraction
"""

from __future__ import annotations

import logging
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..bh_data import BHCurve, generate_bh_pro, parse_dmat_file
from ..geometry import extract_geometry
from ..mapping import resolve_magnet_direction_3d, resolve_material
from ..models import DesignModel, NodeModel, TestModel
from .base import SolveResult, SolverBackend

logger = logging.getLogger(__name__)


class GetDPBackend(SolverBackend):
    """Gmsh + GetDP 3D FEM solver backend.

    Wraps DoSA-3D's script generation logic in Python.
    Requires a STEP file alongside the .dsa3d design file.
    """

    def __init__(self, gmsh_exe: str | None = None, getdp_exe: str | None = None):
        self._gmsh_exe = gmsh_exe or shutil.which("gmsh") or "gmsh"
        self._getdp_exe = getdp_exe or shutil.which("getdp") or "getdp"

    @property
    def name(self) -> str:
        return "getdp"

    @property
    def supported_modes(self) -> list[str]:
        return ["3d"]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(
        self,
        design: DesignModel,
        mode: str = "3d",
        out_dir: str | None = None,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> SolveResult:
        if mode != "3d":
            return SolveResult(
                ok=False, mode=mode, solver="getdp",
                errors=["GetDP backend only supports 3D mode"],
            )

        out_path = Path(out_dir) if out_dir else Path("./output/getdp")
        out_path.mkdir(parents=True, exist_ok=True)

        commands: list[dict[str, Any]] = []
        errors: list[str] = []

        # Extract design metadata
        design_props = self._get_design_properties(design)
        test_props = self._get_test_properties(design, kwargs)
        shape_names: list[str] = design_props.get("shape_names", [])

        if not shape_names:
            shape_names = [p.name for p in design.parts]

        # Find STEP file
        step_file = kwargs.get("step_file") or self._find_step_file(design)
        if step_file:
            step_file = str(Path(step_file).resolve())

        # Load B-H material data
        bh_materials = self._load_bh_materials(design, kwargs)

        # --- Generate scripts ---

        # 1. Define.geo
        define_geo = self._generate_define_geo(shape_names)
        define_geo_path = out_path / "Define.geo"
        define_geo_path.write_text(define_geo, encoding="utf-8")
        commands.append({"method": "generate_define_geo", "args": {"path": str(define_geo_path)}})

        # 2. BH.pro
        steel_parts = [p for p in design.parts if p.kind == "Steel"]
        needed_materials = {p.properties.get("Material", "") for p in steel_parts}
        needed_bh = {k: v for k, v in bh_materials.items() if k in needed_materials}

        bh_pro = generate_bh_pro(needed_bh) if needed_bh else "Function{\n}\n"
        bh_pro_path = out_path / "BH.pro"
        bh_pro_path.write_text(bh_pro, encoding="utf-8")
        commands.append({"method": "generate_bh_pro", "args": {"path": str(bh_pro_path), "materials": list(needed_bh.keys())}})

        # 3. Design.geo
        design_geo = self._generate_design_geo(design, design_props, test_props, step_file)
        geo_path = out_path / "model.geo"
        geo_path.write_text(design_geo, encoding="utf-8")
        commands.append({"method": "generate_design_geo", "args": {"path": str(geo_path)}})

        # 4. Design.pro
        design_pro = self._generate_design_pro(design, design_props, test_props, needed_bh)
        pro_path = out_path / "model.pro"
        pro_path.write_text(design_pro, encoding="utf-8")
        commands.append({"method": "generate_design_pro", "args": {"path": str(pro_path)}})

        if dry_run:
            commands.append({"method": "gmsh (dry-run)", "args": {"file": str(geo_path)}})
            commands.append({"method": "getdp (dry-run)", "args": {"file": str(pro_path)}})
            return SolveResult(ok=True, mode="3d", solver="getdp", commands=commands, errors=[])

        # --- Execute ---

        # Gmsh mesh generation
        gmsh_cmd = [self._gmsh_exe, "-3", str(geo_path.resolve())]
        commands.append({"method": "gmsh", "args": {"cmd": " ".join(gmsh_cmd)}})

        try:
            result = subprocess.run(
                gmsh_cmd, capture_output=True, text=True,
                timeout=300, cwd=str(out_path.resolve()),
            )
            if result.returncode != 0:
                errors.append(f"[gmsh] Exit code {result.returncode}: {result.stderr[:500]}")
        except FileNotFoundError:
            errors.append(f"[gmsh] Executable not found: {self._gmsh_exe}")
            return SolveResult(ok=False, mode="3d", solver="getdp", commands=commands, errors=errors)
        except subprocess.TimeoutExpired:
            errors.append("[gmsh] Timeout after 300s")

        if errors:
            return SolveResult(ok=False, mode="3d", solver="getdp", commands=commands, errors=errors)

        # GetDP solve
        msh_path = (out_path / "model.msh").resolve()
        getdp_cmd = [
            self._getdp_exe, str(pro_path.resolve()),
            "-msh", str(msh_path),
            "-solve", "rsMagStatic_A",
            "-pos", "poMagStatic_A",
        ]
        commands.append({"method": "getdp", "args": {"cmd": " ".join(getdp_cmd)}})

        try:
            result = subprocess.run(
                getdp_cmd, capture_output=True, text=True,
                timeout=600, cwd=str(out_path.resolve()),
            )
            if result.returncode != 0:
                errors.append(f"[getdp] Exit code {result.returncode}: {result.stderr[:500]}")
        except FileNotFoundError:
            errors.append(f"[getdp] Executable not found: {self._getdp_exe}")
        except subprocess.TimeoutExpired:
            errors.append("[getdp] Timeout after 600s")

        # Parse results
        force_data: list[dict[str, Any]] = []
        if not errors:
            force_data = self._parse_force_results(out_path)

        return SolveResult(
            ok=len(errors) == 0, mode="3d", solver="getdp",
            commands=commands, errors=errors, force_data=force_data,
            project_path=str(pro_path) if not errors else None,
        )

    # ------------------------------------------------------------------
    # Design metadata extraction
    # ------------------------------------------------------------------

    def _get_design_properties(self, design: DesignModel) -> dict[str, Any]:
        """Extract design-level properties (bounding box, shape names)."""
        props: dict[str, Any] = {}

        # Navigate to the Design node
        for node in design.nodes:
            for child in node.children:
                if child.kind == "Design":
                    p = child.properties
                    # Shape name order (from AllShapeName)
                    shape_str = p.get("AllShapeName", "")
                    if shape_str:
                        names = [n.strip() for n in shape_str.split(",") if n.strip()]
                        props["shape_names"] = names
                    else:
                        props["shape_names"] = [pt.name for pt in design.parts]

                    # Bounding box
                    props["min_x"] = float(p.get("ShapeMinX", 0))
                    props["max_x"] = float(p.get("ShapeMaxX", 0))
                    props["min_y"] = float(p.get("ShapeMinY", 0))
                    props["max_y"] = float(p.get("ShapeMaxY", 0))
                    props["min_z"] = float(p.get("ShapeMinZ", 0))
                    props["max_z"] = float(p.get("ShapeMaxZ", 0))

                    # Design name
                    props["design_name"] = p.get("DesignName", design.name)
                    break

        if "shape_names" not in props:
            props["shape_names"] = [p.name for p in design.parts]

        return props

    def _get_test_properties(self, design: DesignModel, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Extract test properties (voltage, mesh, moving)."""
        props: dict[str, Any] = {
            "voltage": float(kwargs.get("voltage", 0)),
            "mesh_size_pct": float(kwargs.get("mesh_size_percent", 12.0)),
            "moving_x": float(kwargs.get("moving_x", 0)),
            "moving_y": float(kwargs.get("moving_y", 0)),
            "moving_z": float(kwargs.get("moving_z", 0)),
        }

        # Override from design's ForceTest if available
        if design.tests:
            test = design.tests[0]
            tp = test.properties
            if "Voltage" in tp and props["voltage"] == 0:
                props["voltage"] = float(tp["Voltage"])
            if "MeshSizePercent" in tp:
                props["mesh_size_pct"] = float(tp["MeshSizePercent"])
            if "MovingX" in tp:
                props["moving_x"] = float(tp["MovingX"])
            if "MovingY" in tp:
                props["moving_y"] = float(tp["MovingY"])
            if "MovingZ" in tp:
                props["moving_z"] = float(tp["MovingZ"])

        return props

    # ------------------------------------------------------------------
    # File discovery
    # ------------------------------------------------------------------

    def _find_step_file(self, design: DesignModel) -> str | None:
        """Find the STEP file associated with the design.

        DoSA-3D stores STEP files at: {design_dir}/Shape/{design_name}.step
        """
        if not design.source_file:
            return None

        source = Path(design.source_file)
        design_dir = source.parent
        design_name = source.stem

        # Try Shape subdirectory (DoSA-3D convention)
        step_path = design_dir / "Shape" / f"{design_name}.step"
        if step_path.exists():
            return str(step_path)

        # Try same directory
        step_path = design_dir / f"{design_name}.step"
        if step_path.exists():
            return str(step_path)

        # Try .stp extension
        for ext in [".stp", ".STEP", ".STP"]:
            step_path = design_dir / "Shape" / f"{design_name}{ext}"
            if step_path.exists():
                return str(step_path)

        return None

    def _load_bh_materials(
        self, design: DesignModel, kwargs: dict[str, Any],
    ) -> dict[str, BHCurve]:
        """Load B-H material data from .dmat file."""
        # Try explicit path from kwargs
        dmat_path = kwargs.get("dmat_file")
        if dmat_path:
            return parse_dmat_file(dmat_path)

        # Try DoSA-3D Materials directory relative to source file
        if design.source_file:
            source = Path(design.source_file)
            # Navigate up to find Materials directory
            for parent in source.parents:
                candidate = parent / "Materials" / "DoSA_MS.dmat"
                if candidate.exists():
                    return parse_dmat_file(candidate.resolve())

        # Fallback to bundled data
        return parse_dmat_file(None)

    # ------------------------------------------------------------------
    # Define.geo generation
    # ------------------------------------------------------------------

    def _generate_define_geo(self, shape_names: list[str]) -> str:
        """Generate Define.geo — part name to integer ID mapping.

        Replicates DoSA-3D createDefineGeoFile().
        """
        lines = [
            "// Auto-generated by moa_actuator (DoSA-3D wrapper)",
            "",
            "mm = 1e-3;",
            "",
            "AIR = 199;",
            "SKIN_AIR = 399;",
            "",
            "SKIN_MOVING = 301;",
            "SKIN_STEEL = 302;",
            "",
        ]

        # Part IDs start from 1 (Gmsh Volume index convention)
        for i, name in enumerate(shape_names, 1):
            lines.append(f"{name.upper()} = {i};")

        lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Design.geo generation (STEP import + Air region)
    # ------------------------------------------------------------------

    def _generate_design_geo(
        self,
        design: DesignModel,
        design_props: dict[str, Any],
        test_props: dict[str, Any],
        step_file: str | None,
    ) -> str:
        """Generate Design.geo — geometry import, meshing, air region.

        Replicates DoSA-3D createDesignGeoFile().
        """
        shape_names: list[str] = design_props.get("shape_names", [])
        mesh_pct = test_props.get("mesh_size_pct", 12.0)
        moving_x = test_props.get("moving_x", 0)
        moving_y = test_props.get("moving_y", 0)
        moving_z = test_props.get("moving_z", 0)

        lines = [
            '// Auto-generated by moa_actuator (DoSA-3D wrapper)',
            'SetFactory("OpenCASCADE");',
            '',
            'Include "Define.geo";',
            '',
            'Mesh.Optimize = 1;',
            'Mesh.VolumeEdges = 0;',
            'Solver.AutoMesh = 2;',
            '',
        ]

        if step_file:
            # STEP import (DoSA-3D m_str21_Import_Script)
            step_path_str = step_file.replace("\\", "/")
            lines.append(f'Merge "{step_path_str}";')
            lines.append('')
            lines.append("STEP_Volumes[] = Volume '*';")
            lines.append('')
            lines.append('Dilate { {0, 0, 0}, {mm, mm, mm} } { Volume{STEP_Volumes[]}; }')
            lines.append('')

            # Map STEP volumes to named parts (0-indexed in STEP)
            for i, name in enumerate(shape_names):
                lines.append(f"vol{name} = STEP_Volumes[{i}];")
            lines.append('')

            # Identify moving/steel parts
            moving_parts: list[str] = []
            steel_parts: list[str] = []
            for part in design.parts:
                if part.properties.get("MovingParts", "") == "MOVING":
                    moving_parts.append(part.name)
                if part.kind == "Steel":
                    steel_parts.append(part.name)

            # Move moving parts
            if moving_parts and (moving_x != 0 or moving_y != 0 or moving_z != 0):
                vol_list = ", ".join(f"vol{n}" for n in moving_parts)
                lines.append(
                    f"Translate {{ {moving_x}*mm , {moving_y}*mm, "
                    f"{moving_z}*mm }} {{ Volume{{ {vol_list} }}; }}"
                )
                lines.append('')

            # Skin boundaries
            if moving_parts:
                vol_list = ", ".join(f"vol{n}" for n in moving_parts)
                lines.append(f"skinMoving() = CombinedBoundary{{ Volume{{ {vol_list} }}; }};")

            if steel_parts:
                vol_list = ", ".join(f"vol{n}" for n in steel_parts)
                lines.append(f"skinSteel() = CombinedBoundary{{ Volume{{ {vol_list} }}; }};")
                lines.append('')

            # Physical volumes for each part
            for name in shape_names:
                lines.append(f"Physical Volume({name.upper()}) = vol{name};")
            lines.append('')

            # Air region
            self._add_air_region(lines, design_props, mesh_pct, steel_parts, moving_parts)
        else:
            # No STEP file — fallback with warning
            lines.append("// WARNING: No STEP file found.")
            lines.append("// Provide a STEP file via step_file parameter for accurate 3D analysis.")
            lines.append("// Attempting revolve from 2D cross-sections...")
            lines.append("")
            self._add_revolve_geometry(lines, design, design_props, test_props, mesh_pct)

        return "\n".join(lines)

    def _add_air_region(
        self,
        lines: list[str],
        design_props: dict[str, Any],
        mesh_pct: float,
        steel_parts: list[str],
        moving_parts: list[str],
    ) -> None:
        """Add outer/inner air region boxes.

        Replicates DoSA-3D's air region: 150% outer padding, 20% inner padding.
        """
        min_x = design_props.get("min_x", -10)
        max_x = design_props.get("max_x", 10)
        min_y = design_props.get("min_y", -10)
        max_y = design_props.get("max_y", 10)
        min_z = design_props.get("min_z", -10)
        max_z = design_props.get("max_z", 10)

        len_x = abs(max_x - min_x)
        len_y = abs(max_y - min_y)
        len_z = abs(max_z - min_z)
        avg_len = (len_x + len_y + len_z) / 3.0

        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        cz = (min_z + max_z) / 2.0

        # Mesh size (DoSA-3D: cube_root(volume) * pct/100, converted to m)
        vol_size = len_x * len_y * len_z
        mesh_size = (vol_size ** (1.0 / 3.0)) * mesh_pct / 100.0
        mesh_size_m = mesh_size / 1000.0

        # Outer box: 150% padding each side
        outer_pad = avg_len * 1.5
        outer_min = cx - avg_len / 2.0 - outer_pad
        outer_min_y = cy - avg_len / 2.0 - outer_pad
        outer_min_z = cz - avg_len / 2.0 - outer_pad
        outer_len = avg_len + outer_pad * 2.0

        # Inner box: 20% padding each side
        inner_pad_x = len_x * 0.2
        inner_pad_y = len_y * 0.2
        inner_pad_z = len_z * 0.2
        inner_min_x = cx - len_x / 2.0 - inner_pad_x
        inner_min_y = cy - len_y / 2.0 - inner_pad_y
        inner_min_z = cz - len_z / 2.0 - inner_pad_z
        inner_len_x = len_x + inner_pad_x * 2.0
        inner_len_y = len_y + inner_pad_y * 2.0
        inner_len_z = len_z + inner_pad_z * 2.0

        lines.append("// === Air Region ===")
        lines.append(
            f"volOuterBox = newv; Box(newv) = {{ "
            f"{outer_min}*mm, {outer_min_y}*mm, {outer_min_z}*mm, "
            f"{outer_len}*mm, {outer_len}*mm, {outer_len}*mm }};"
        )
        lines.append(
            f"volInnerBox = newv; Box(newv) = {{ "
            f"{inner_min_x}*mm, {inner_min_y}*mm, {inner_min_z}*mm, "
            f"{inner_len_x}*mm, {inner_len_y}*mm, {inner_len_z}*mm }};"
        )
        lines.append("")
        lines.append(
            "volOuterAir = newv; BooleanDifference(newv) = "
            "{ Volume{volOuterBox}; Delete; }{ Volume{volInnerBox}; };"
        )
        lines.append(
            "volInnerAir = newv; BooleanDifference(newv) = "
            "{ Volume{volInnerBox}; Delete; }{ Volume{STEP_Volumes()}; };"
        )
        lines.append("")
        lines.append("BooleanFragments{ Volume{volOuterAir, volInnerAir}; Delete; }{}")
        lines.append("BooleanFragments{ Volume{volInnerAir, STEP_Volumes()}; Delete; }{}")
        lines.append("")

        lines.append(f"Characteristic Length {{ PointsOf{{ Volume{{volOuterAir}}; }} }} = {mesh_size_m} * 8.0;")
        lines.append(f"Characteristic Length {{ PointsOf{{ Volume{{volInnerAir}}; }} }} = {mesh_size_m} * 2.0;")
        lines.append(f"Characteristic Length {{ PointsOf{{ Volume{{STEP_Volumes[]}}; }} }} = {mesh_size_m} * 1.0;")
        lines.append("")

        if moving_parts:
            lines.append("Physical Surface(SKIN_MOVING) = skinMoving();")
        if steel_parts:
            lines.append("Physical Surface(SKIN_STEEL) = skinSteel();")
        lines.append("")

        lines.append("volAll() = Volume '*';")
        lines.append("skinAir() = CombinedBoundary{ Volume{ volAll() }; };")
        lines.append("")
        lines.append("Physical Volume(AIR) = {volInnerAir, volOuterAir};")
        lines.append("Physical Surface(SKIN_AIR) = skinAir();")
        lines.append("")

    def _add_revolve_geometry(
        self,
        lines: list[str],
        design: DesignModel,
        design_props: dict[str, Any],
        test_props: dict[str, Any],
        mesh_pct: float,
    ) -> None:
        """Fallback: generate 3D geometry by revolving 2D cross-sections."""
        mesh_size_m = 0.002
        moving_parts: list[str] = []
        steel_parts: list[str] = []

        point_counter = 1
        line_counter = 1
        ll_counter = 1
        surf_counter = 1

        for part in design.parts:
            geom = extract_geometry(part)
            if not geom or not geom.is_valid:
                continue

            if part.properties.get("MovingParts", "") == "MOVING":
                moving_parts.append(part.name)
            if part.kind == "Steel":
                steel_parts.append(part.name)

            pts = geom.to_polyline_points(unit_scale=1.0)
            lines.append(f"// Part: {part.name}")

            point_ids = []
            for pt in pts:
                lines.append(f"Point({point_counter}) = {{{pt[0]}*mm, {pt[1]}*mm, 0, {mesh_size_m}}};")
                point_ids.append(point_counter)
                point_counter += 1

            line_ids = []
            for j in range(len(point_ids)):
                p1 = point_ids[j]
                p2 = point_ids[(j + 1) % len(point_ids)]
                lines.append(f"Line({line_counter}) = {{{p1}, {p2}}};")
                line_ids.append(line_counter)
                line_counter += 1

            line_list = ", ".join(str(lid) for lid in line_ids)
            lines.append(f"Curve Loop({ll_counter}) = {{{line_list}}};")
            lines.append(f"Plane Surface({surf_counter}) = {{{ll_counter}}};")
            lines.append(f"Extrude {{ {{0, 1, 0}}, {{0, 0, 0}}, 2*Pi }} {{ Surface{{{surf_counter}}}; }}")
            lines.append(f"vol{part.name} = newv - 1;")
            lines.append(f"Physical Volume({part.name.upper()}) = vol{part.name};")
            lines.append("")

            ll_counter += 1
            surf_counter += 1

        # Simplified air region
        lines.append("// Simplified air region")
        lines.append("volAirBox = newv; Sphere(newv) = {0, 0, 0, 0.1};")
        lines.append("Physical Volume(AIR) = {volAirBox};")
        lines.append("skinAir() = CombinedBoundary{ Volume{ volAirBox }; };")
        lines.append("Physical Surface(SKIN_AIR) = skinAir();")
        if moving_parts:
            vol_list = ", ".join(f"vol{n}" for n in moving_parts)
            lines.append(f"skinMoving() = CombinedBoundary{{ Volume{{ {vol_list} }}; }};")
            lines.append("Physical Surface(SKIN_MOVING) = skinMoving();")
        lines.append("")
        lines.append("Mesh 3;")

    # ------------------------------------------------------------------
    # Design.pro generation (complete FEM problem)
    # ------------------------------------------------------------------

    def _generate_design_pro(
        self,
        design: DesignModel,
        design_props: dict[str, Any],
        test_props: dict[str, Any],
        bh_materials: dict[str, BHCurve],
    ) -> str:
        """Generate Design.pro — complete GetDP problem definition.

        Replicates DoSA-3D's full .pro file generation.
        """
        shape_names: list[str] = design_props.get("shape_names", [])
        voltage = test_props.get("voltage", 0)

        steel_parts = [p for p in design.parts if p.kind == "Steel"]
        coil_parts = [p for p in design.parts if p.kind == "Coil"]
        magnet_parts = [p for p in design.parts if p.kind == "Magnet"]

        has_steel = len(steel_parts) > 0
        has_magnets = len(magnet_parts) > 0

        lines: list[str] = []

        lines.append('// Auto-generated by moa_actuator (DoSA-3D wrapper)')
        lines.append('Include "Define.geo";')
        lines.append('Include "BH.pro";')
        lines.append('')

        self._add_group_section(lines, shape_names, steel_parts, coil_parts, magnet_parts)
        self._add_function_section(lines, design, design_props, test_props, bh_materials,
                                   steel_parts, coil_parts, magnet_parts, voltage)
        self._add_constraint_section(lines)

        coil_name = coil_parts[0].name if coil_parts else "Coil"
        self._add_formulation_section(lines, coil_name, has_steel, has_magnets)
        self._add_resolution_section(lines)
        self._add_postprocessing_section(lines, coil_name)
        self._add_postoperation_section(lines, coil_name)

        return "\n".join(lines)

    def _add_group_section(
        self,
        lines: list[str],
        shape_names: list[str],
        steel_parts: list[NodeModel],
        coil_parts: list[NodeModel],
        magnet_parts: list[NodeModel],
    ) -> None:
        lines.append("Group {")
        lines.append("    volAir  = Region[AIR];")
        lines.append("    skinAir = Region[SKIN_AIR];")
        lines.append("")
        lines.append("    skinMoving = Region[SKIN_MOVING];")
        lines.append("    skinSteel = Region[SKIN_STEEL];")
        lines.append("")

        for name in shape_names:
            lines.append(f"    vol{name} = Region[{name.upper()}];")
        lines.append("")

        nl_parts = ", ".join(f"vol{p.name}" for p in steel_parts)
        l_parts_list = ["volAir"] + [f"vol{p.name}" for p in coil_parts + magnet_parts]
        l_parts = ", ".join(l_parts_list)

        domain_all_parts = []
        if nl_parts:
            lines.append(f"    domainNL = Region[ {{{nl_parts}}} ];")
            domain_all_parts.append("domainNL")
        if l_parts:
            lines.append(f"    domainL = Region[ {{{l_parts}}} ];")
            domain_all_parts.append("domainL")
        lines.append(f"    domainALL = Region[ {{{', '.join(domain_all_parts)}}} ];")
        lines.append("")

        if magnet_parts:
            mag_list = ", ".join(f"vol{p.name}" for p in magnet_parts)
            lines.append(f"    domainMagnet = Region[ {{{mag_list}}} ];")
            lines.append("")

        lines.append("}")
        lines.append("")

    def _add_function_section(
        self,
        lines: list[str],
        design: DesignModel,
        design_props: dict[str, Any],
        test_props: dict[str, Any],
        bh_materials: dict[str, BHCurve],
        steel_parts: list[NodeModel],
        coil_parts: list[NodeModel],
        magnet_parts: list[NodeModel],
        voltage: float,
    ) -> None:
        """Function { ... } — mu, nu, js0[], hc, br, TM[]"""
        lines.append("Function {")
        lines.append("")
        lines.append("    mu0 = 4*Pi*1e-7;")
        lines.append("")
        lines.append("    Nb_max_iter = 30;")
        lines.append("    stop_criterion = 1e-5;")
        lines.append("    relaxation_factor = 1.0;")
        lines.append("")
        lines.append("    mu[volAir] = mu0;")
        lines.append("    nu[volAir] = 1.0/mu0;")
        lines.append("")

        # --- Coil current density (DoSA-3D addFuncitonToDesignProFile) ---
        for coil in coil_parts:
            props = coil.properties
            turns = int(props.get("Turns", 0))
            resistance = float(props.get("Resistance", 1))
            inner_d = float(props.get("InnerDiameter", 0))
            outer_d = float(props.get("OuterDiameter", 0))
            height = float(props.get("Height", 0))
            direction = props.get("CurrentDirection", "CounterClockwise")

            current = voltage / resistance if resistance > 0 else 0
            coil_width = (outer_d - inner_d) / 2.0
            coil_area = (coil_width * height) / 1e6  # mm² → m²

            # Center position (mm → m)
            cx = (design_props.get("min_x", 0) + design_props.get("max_x", 0)) / 2.0 * 0.001
            cz = (design_props.get("min_z", 0) + design_props.get("max_z", 0)) / 2.0 * 0.001

            lines.append(f"    // Coil: {coil.name}")
            lines.append(f"    mu[vol{coil.name}] = mu0;")
            lines.append(f"    nu[vol{coil.name}] = 1.0/mu0;")
            lines.append("")
            lines.append(f"    current = {current};")
            lines.append(f"    coilTurns = {turns};")
            lines.append("")
            lines.append(f"    coilTurns[] = coilTurns;")
            lines.append("")
            lines.append(f"    areaCoilSection[] = {coil_area};")
            lines.append("")

            if direction == "CounterClockwise":
                lines.append(
                    f"    vectorCurrent[] = Vector[ "
                    f"Cos[Atan2[X[]-({cx}), Z[]-({cz})]], 0, "
                    f"-Sin[Atan2[X[]-({cx}), Z[]-({cz})]]];")
            else:
                lines.append(
                    f"    vectorCurrent[] = - Vector[ "
                    f"Cos[Atan2[X[]-({cx}), Z[]-({cz})]], 0, "
                    f"-Sin[Atan2[X[]-({cx}), Z[]-({cz})]]];")
            lines.append("")
            lines.append("    js0[] = current * coilTurns[] / areaCoilSection[] * vectorCurrent[];")
            lines.append("")

        # --- Magnet Hc/Br ---
        for mag in magnet_parts:
            props = mag.properties
            hc = float(props.get("Hc", 0))
            br = float(props.get("Br", 0))
            rot_axis = props.get("emMagnetRotationAxis", "Z")
            rot_angle = float(props.get("MagnetRotationAngle", 0))

            if hc == 0:
                continue

            mur = br / hc if hc != 0 else 1.05
            angle_rad = rot_angle * math.pi / 180.0

            if rot_axis.upper().endswith("Z_AXIS") or rot_axis.upper() == "Z":
                hc_x, hc_y, hc_z = hc * math.cos(angle_rad), hc * math.sin(angle_rad), 0.0
                br_x, br_y, br_z = br * math.cos(angle_rad), br * math.sin(angle_rad), 0.0
            else:
                hc_x, hc_y, hc_z = hc * math.cos(angle_rad), 0.0, -hc * math.sin(angle_rad)
                br_x, br_y, br_z = br * math.cos(angle_rad), 0.0, -br * math.sin(angle_rad)

            lines.append(f"    // Magnet: {mag.name}")
            lines.append(f"    hc[vol{mag.name}] = Vector[{-hc_x}, {-hc_y}, {-hc_z}];")
            lines.append(f"    br[vol{mag.name}] = Vector[{-br_x}, {-br_y}, {-br_z}];")
            lines.append(f"    mu[vol{mag.name}] = {mur};")
            lines.append(f"    nu[vol{mag.name}] = 1.0 / {mur};")
            lines.append("")

        # --- Steel nonlinear nu (from B-H data) ---
        for steel in steel_parts:
            mat_name = steel.properties.get("Material", "")
            if mat_name and mat_name in bh_materials:
                lines.append(f"    nu[vol{steel.name}] = nu_{mat_name}[$1];")
                lines.append(f"    dhdb_NL[vol{steel.name}] = dhdb_{mat_name}[$1];")
                lines.append("")
            else:
                lines.append(f"    // Steel: {steel.name} (linearized — no B-H data for '{mat_name}')")
                lines.append(f"    mu[vol{steel.name}] = 1000 * mu0;")
                lines.append(f"    nu[vol{steel.name}] = 1.0 / (1000 * mu0);")
                lines.append("")

        lines.append("    TM[] = ( SquDyadicProduct[$1] - SquNorm[$1] * TensorDiag[0.5, 0.5, 0.5] ) / mu[];")
        lines.append("}")
        lines.append("")

    def _add_constraint_section(self, lines: list[str]) -> None:
        """Constraint, FunctionSpace, Jacobian, Integration — exact DoSA-3D replica."""
        lines.append("Constraint {")
        lines.append("    { Name cstDirichlet_A_0 ;")
        lines.append("        Case {")
        lines.append("            { Region skinAir ; Type Assign ; Value 0. ; }")
        lines.append("        }")
        lines.append("    }")
        lines.append("")
        lines.append("    { Name cstForceMoving;")
        lines.append("        Case {")
        lines.append("            { Region skinMoving ; Value 1. ; }")
        lines.append("        }")
        lines.append("    }")
        lines.append("")
        lines.append("    { Name cstGaugeCondition_A ; Type Assign ;")
        lines.append("        Case {")
        lines.append("            { Region domainALL ; SubRegion skinAir ; Value 0. ; }")
        lines.append("        }")
        lines.append("    }")
        lines.append("}")
        lines.append("")
        lines.append("FunctionSpace {")
        lines.append("")
        lines.append("    { Name fsHcurl_A_3D ; Type Form1 ;")
        lines.append("        BasisFunction {")
        lines.append("            { Name se ; NameOfCoef ae ; Function BF_Edge ;")
        lines.append("                Support domainALL ; Entity EdgesOf[ All ] ; }")
        lines.append("        }")
        lines.append("        Constraint {")
        lines.append("            { NameOfCoef ae;    EntityType EdgesOf ; NameOfConstraint cstDirichlet_A_0 ; }")
        lines.append("")
        lines.append("            { NameOfCoef ae  ;    EntityType EdgesOfTreeIn ; EntitySubType StartingOn ;")
        lines.append("                 NameOfConstraint cstGaugeCondition_A ; }")
        lines.append("        }")
        lines.append("    }")
        lines.append("")
        lines.append("    { Name fsForceMoving ; Type Form0 ;")
        lines.append("        BasisFunction {")
        lines.append("            { Name sn ; NameOfCoef un ; Function BF_GroupOfNodes ;")
        lines.append("              Support volAir ; Entity GroupsOfNodesOf[ skinMoving ] ; }")
        lines.append("        }")
        lines.append("        Constraint {")
        lines.append("            { NameOfCoef un ; EntityType GroupsOfNodesOf ; NameOfConstraint cstForceMoving ; }")
        lines.append("        }")
        lines.append("    }")
        lines.append("}")
        lines.append("")
        lines.append("Jacobian {")
        lines.append("    { Name jbVolume ;")
        lines.append("        Case {")
        lines.append("            { Region All ;       Jacobian Vol ; }")
        lines.append("        }")
        lines.append("    }")
        lines.append("}")
        lines.append("")
        lines.append("Integration {")
        lines.append("    { Name igElement ;")
        lines.append("        Case {")
        lines.append("            {    Type Gauss ;")
        lines.append("                Case {")
        lines.append("                    { GeoElement Triangle    ; NumberOfPoints  4 ; }")
        lines.append("                    { GeoElement Quadrangle  ; NumberOfPoints  4 ; }")
        lines.append("                    { GeoElement Tetrahedron ; NumberOfPoints  4 ; }")
        lines.append("                }")
        lines.append("            }")
        lines.append("        }")
        lines.append("    }")
        lines.append("}")
        lines.append("")

    def _add_formulation_section(
        self, lines: list[str], coil_name: str,
        has_steel: bool, has_magnets: bool,
    ) -> None:
        """Formulation — replicates DoSA-3D m_str33_Formulation_Resolution_Script."""
        lines.append("Formulation {")
        lines.append("")
        lines.append("    { Name fmMagStatic_A; Type FemEquation;")
        lines.append("        Quantity {")
        lines.append("            { Name qnt_A; Type Local; NameOfSpace fsHcurl_A_3D; }")
        lines.append("            { Name qnt_MovingForce ; Type Local ; NameOfSpace fsForceMoving ; }")
        lines.append("        }")
        lines.append("        Equation {")
        lines.append("            Integral { [ nu[{d qnt_A}] * Dof{d qnt_A} , {d qnt_A} ] ;")
        lines.append("                In domainALL ; Jacobian jbVolume ; Integration igElement ; }")
        lines.append("")

        if has_steel:
            lines.append("            Galerkin { JacNL[dhdb_NL[{d qnt_A}] * Dof{d qnt_A} , {d qnt_A} ] ;")
            lines.append("                In domainNL ; Jacobian jbVolume ; Integration igElement ; }")
            lines.append("")

        if has_magnets:
            lines.append("            Galerkin { [ nu[] * br[] , {d qnt_A} ] ;")
            lines.append("                In domainMagnet ; Jacobian jbVolume ; Integration igElement ; }")
            lines.append("")

        lines.append(f"            Galerkin {{ [ -js0[], {{qnt_A}} ] ;")
        lines.append(f"                In vol{coil_name} ; Jacobian jbVolume ; Integration igElement ; }}")
        lines.append("")
        lines.append("            Galerkin { [ 0 * Dof{qnt_MovingForce} , {qnt_MovingForce} ] ;")
        lines.append("                In volAir ; Jacobian jbVolume ; Integration igElement ; }")
        lines.append("")
        lines.append("        }")
        lines.append("    }")
        lines.append("}")
        lines.append("")

    def _add_resolution_section(self, lines: list[str]) -> None:
        lines.append("Resolution {")
        lines.append("    { Name rsMagStatic_A ;")
        lines.append("        System {")
        lines.append("            { Name sys_A ; NameOfFormulation fmMagStatic_A ; }")
        lines.append("        }")
        lines.append("")
        lines.append("        Operation {")
        lines.append("            IterativeLoop[Nb_max_iter, stop_criterion, relaxation_factor]{")
        lines.append("                GenerateJac[sys_A] ; SolveJac[sys_A] ; }")
        lines.append("            SaveSolution[sys_A] ;")
        lines.append("        }")
        lines.append("    }")
        lines.append("}")
        lines.append("")

    def _add_postprocessing_section(self, lines: list[str], coil_name: str) -> None:
        """PostProcessing — replicates DoSA-3D m_str41_PostProcessing_Script."""
        lines.append("PostProcessing {")
        lines.append("")
        lines.append("    { Name ppMagStatic_A ; NameOfFormulation fmMagStatic_A ;")
        lines.append("        PostQuantity {")
        lines.append("")
        lines.append("            { Name b ; Value {")
        lines.append("                Term { [ {d qnt_A} ]; In domainALL; Jacobian jbVolume; }")
        lines.append("                }")
        lines.append("            }")
        lines.append("")
        lines.append(f"            {{ Name js ; Value {{")
        lines.append(f"                Term {{ [ js0[] ] ; In vol{coil_name} ; Jacobian jbVolume ; }}")
        lines.append(f"                }}")
        lines.append(f"            }}")
        lines.append("")
        lines.append("            { Name psMovingForce ; Value {")
        lines.append("                Term { [ {qnt_MovingForce} ] ; In domainALL ; Jacobian jbVolume ; }")
        lines.append("                }")
        lines.append("            }")
        lines.append("            { Name forceMoving ; Value {")
        lines.append("                Integral { [ - TM[{d qnt_A}] * {d qnt_MovingForce} ] ;")
        lines.append("                    In volAir ; Jacobian jbVolume ; Integration igElement ; }")
        lines.append("                }")
        lines.append("            }")
        lines.append("            { Name forceMovingX ; Value {")
        lines.append("                Integral { [ CompX[- TM[{d qnt_A}] * {d qnt_MovingForce} ] ] ;")
        lines.append("                    In volAir ; Jacobian jbVolume ; Integration igElement ; }")
        lines.append("                }")
        lines.append("            }")
        lines.append("            { Name forceMovingY ; Value {")
        lines.append("                Integral { [ CompY[- TM[{d qnt_A}] * {d qnt_MovingForce} ] ] ;")
        lines.append("                    In volAir ; Jacobian jbVolume ; Integration igElement ; }")
        lines.append("                }")
        lines.append("            }")
        lines.append("            { Name forceMovingZ ; Value {")
        lines.append("                Integral { [ CompZ[- TM[{d qnt_A}] * {d qnt_MovingForce} ] ] ;")
        lines.append("                    In volAir ; Jacobian jbVolume ; Integration igElement ; }")
        lines.append("                }")
        lines.append("            }")
        lines.append("        }")
        lines.append("    }")
        lines.append("}")
        lines.append("")

    def _add_postoperation_section(self, lines: list[str], coil_name: str) -> None:
        """PostOperation — replicates DoSA-3D m_str42_PostOperation_Script."""
        lines.append("PostOperation {")
        lines.append("    { Name poMagStatic_A ; NameOfPostProcessing ppMagStatic_A;")
        lines.append("        Operation {")
        lines.append("")
        lines.append(f'            Print[ js, OnElementsOf vol{coil_name}, File "js.pos" ] ;')
        lines.append('            Print[ b, OnElementsOf domainALL, File "b.pos" ] ;')
        lines.append("")
        lines.append('            DeleteFile ["F.dat"];')
        lines.append('            DeleteFile ["Fx.dat"];')
        lines.append('            DeleteFile ["Fy.dat"];')
        lines.append('            DeleteFile ["Fz.dat"];')
        lines.append("")
        lines.append('            Print[ forceMoving[volAir], OnGlobal, Format Table, File > "F.dat" ];')
        lines.append("")
        lines.append('            Print[ forceMovingX[volAir], OnGlobal, Format Table, File > "Fx.dat",')
        lines.append('              SendToServer Sprintf("Output/Coil %g/X force [N]", 1), Color "Ivory"  ];')
        lines.append("")
        lines.append('            Print[ forceMovingY[volAir], OnGlobal, Format Table, File > "Fy.dat",')
        lines.append('              SendToServer Sprintf("Output/Coil %g/Y force [N]", 1), Color "Ivory"  ];')
        lines.append("")
        lines.append('            Print[ forceMovingZ[volAir], OnGlobal, Format Table, File > "Fz.dat",')
        lines.append('              SendToServer Sprintf("Output/Coil %g/Z force [N]", 1), Color "Ivory"  ];')
        lines.append("        }")
        lines.append("    }")
        lines.append("}")
        lines.append("")

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    def _parse_force_results(self, out_path: Path) -> list[dict[str, Any]]:
        """Parse F.dat, Fx.dat, Fy.dat, Fz.dat files."""
        result: dict[str, float] = {"Fx": 0.0, "Fy": 0.0, "Fz": 0.0}

        for component, filename in [("Fx", "Fx.dat"), ("Fy", "Fy.dat"), ("Fz", "Fz.dat")]:
            fpath = out_path / filename
            if fpath.exists():
                try:
                    text = fpath.read_text(encoding="utf-8").strip()
                    for line in text.splitlines():
                        parts = line.strip().split()
                        if parts:
                            result[component] = float(parts[-1])
                except (ValueError, IndexError):
                    pass

        return [result]
