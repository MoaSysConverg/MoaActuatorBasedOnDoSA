"""Maxwell backend using PyAEDT (Maxwell2d + Maxwell3d)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..geometry import Geometry2D, extract_geometry, geometry_from_coil_params
from ..mapping import resolve_magnet_direction, resolve_material
from ..models import DesignModel, NodeModel
from .base import SolveResult, SolverBackend

logger = logging.getLogger(__name__)


class MaxwellBackend(SolverBackend):
    """PyAEDT-based Maxwell solver backend (2D and 3D).

    For 2D axisymmetric:
    - solution_type should be "MagnetostaticZ" (or "TransientZ")
    - Geometry is placed in the XZ plane: X=radius, Z=axial
    - pyAEDT maps "MagnetostaticZ" → Magnetostatic about Z

    For 3D:
    - 2D cross-section is revolved around Z axis
    """

    def __init__(
        self,
        aedt_version: str = "2026.1",
        non_graphical: bool = True,
        new_desktop: bool = True,
        solution_type: str = "MagnetostaticZ",
    ):
        self.aedt_version = aedt_version
        self.non_graphical = non_graphical
        self.new_desktop = new_desktop
        self.solution_type = solution_type

    @property
    def name(self) -> str:
        return "maxwell"

    @property
    def supported_modes(self) -> list[str]:
        return ["2d", "3d"]

    def solve(
        self,
        design: DesignModel,
        mode: str = "2d",
        out_dir: str | None = None,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> SolveResult:
        out_path = Path(out_dir) if out_dir else Path("./output")
        out_path.mkdir(parents=True, exist_ok=True)

        commands: list[dict[str, Any]] = []
        errors: list[str] = []

        project_name = design.name or "DoSA_Project"
        project_file = str((out_path / f"{project_name}.aedt").resolve())

        app = None
        if not dry_run:
            app = self._create_session(project_file, project_name, mode, errors)

        # Build geometry
        # For 2D axisymmetric (about Z): geometry in XZ plane [R, 0, Z]
        # For 3D: geometry in XY plane then revolve around Z
        geom_plane = "XZ" if mode == "2d" else "XY"

        for part in design.parts:
            geom = self._extract_part_geometry(part)
            if geom is None or not geom.is_valid:
                errors.append(f"[geometry] No valid shape for '{part.name}'")
                continue

            pts = geom.to_polyline_points(plane=geom_plane)
            cmd = {"method": "create_polyline", "args": {"name": geom.name, "points_count": len(pts), "plane": geom_plane}}
            commands.append(cmd)

            if app:
                try:
                    poly = app.modeler.create_polyline(
                        points=pts, close_surface=True, cover_surface=True, name=geom.name,
                    )
                    if poly is None:
                        errors.append(f"[geometry] create_polyline returned None for '{geom.name}'")
                        continue
                except Exception as exc:
                    errors.append(f"[geometry] create_polyline '{geom.name}': {exc}")
                    continue

            if mode == "3d":
                cmd_rev = {"method": "sweep_around_axis", "args": {"name": geom.name, "axis": "Z", "angle": 360}}
                commands.append(cmd_rev)
                if app:
                    try:
                        app.modeler.sweep_around_axis(assignment=geom.name, axis="Z", sweep_angle=360)
                    except Exception as exc:
                        errors.append(f"[geometry] sweep_around_axis '{geom.name}': {exc}")

        # Assign materials
        for part in design.parts:
            mat_str = part.properties.get("Material", "")
            if not mat_str:
                continue
            try:
                mat = resolve_material(mat_str)
            except ValueError as exc:
                errors.append(f"[material] {exc}")
                continue

            cmd_mat = {"method": "assign_material", "args": {"name": part.name, "material": mat.maxwell_name}}
            commands.append(cmd_mat)

            if app:
                try:
                    app.assign_material(assignment=[part.name], material=mat.maxwell_name)
                except Exception as exc:
                    errors.append(f"[material] '{part.name}': {exc}")

        # Excitations (coils)
        for part in design.parts:
            if part.kind != "Coil":
                continue
            props = part.properties
            turns = int(props.get("Turns", 0))
            polarity = "Positive" if props.get("CurrentDirection", "IN") == "IN" else "Negative"

            cmd_coil = {"method": "assign_coil", "args": {"name": part.name, "turns": turns, "polarity": polarity}}
            commands.append(cmd_coil)

            if app:
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

        # Create setup
        cmd_setup = {"method": "create_setup", "args": {"solution_type": self.solution_type}}
        commands.append(cmd_setup)

        if app:
            try:
                setup = app.create_setup(name="MoA_Setup")
                if self.solution_type.startswith("Transient"):
                    setup.props["StopTime"] = kwargs.get("stop_time", "20ms")
                    setup.props["TimeStep"] = kwargs.get("time_step", "0.2ms")
                else:
                    setup.props["MaximumPasses"] = 10
                    setup.props["PercentRefinement"] = 30
                setup.update()
            except Exception as exc:
                errors.append(f"[setup] create_setup: {exc}")

        if app:
            try:
                app.save_project()
            except Exception:
                pass

        return SolveResult(
            ok=len(errors) == 0,
            mode=mode,
            solver="maxwell",
            commands=commands,
            errors=errors,
            project_path=project_file if not dry_run else None,
        )

    def _create_session(
        self, project_file: str, design_name: str, mode: str, errors: list[str]
    ) -> Any:
        """Create Maxwell2d/3d session.

        For 2D: solution_type like "MagnetostaticZ" maps to
        Magnetostatic about Z in pyAEDT.
        """
        # pyAEDT accepts "MagnetostaticZ" directly for 2D about-Z
        solution = self.solution_type

        try:
            if mode == "2d":
                from ansys.aedt.core import Maxwell2d
                app = Maxwell2d(
                    project=project_file,
                    design=design_name,
                    solution_type=solution,
                    non_graphical=self.non_graphical,
                    new_desktop=self.new_desktop,
                    remove_lock=True,
                )
            else:
                from ansys.aedt.core import Maxwell3d
                # For 3D, strip the trailing "Z" — use plain "Magnetostatic"/"Transient"
                solution_3d = solution.rstrip("Zz") if solution.endswith(("Z", "z")) else solution
                app = Maxwell3d(
                    project=project_file,
                    design=design_name,
                    solution_type=solution_3d,
                    non_graphical=self.non_graphical,
                    new_desktop=self.new_desktop,
                    remove_lock=True,
                )
            app.modeler.model_units = "mm"
            return app
        except (ImportError, ModuleNotFoundError):
            errors.append("[session] PyAEDT not available")
            return None
        except Exception as exc:
            errors.append(f"[session] Maxwell init failed: {exc}")
            return None

    def _extract_part_geometry(self, part: NodeModel) -> Geometry2D | None:
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
