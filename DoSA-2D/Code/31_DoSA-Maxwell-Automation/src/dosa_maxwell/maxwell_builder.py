"""Maxwell session builder — creates and configures an Ansys Maxwell project from DoSA data.

This module bridges the canonical DoSA model to PyAEDT Maxwell2d/3d API calls.
When PyAEDT is not available, it produces a detailed execution plan (script log)
that documents every API call that *would* be made.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .geometry import Geometry2D, Point2D, extract_geometry, geometry_from_coil_params
from .mapping import MaterialInfo, resolve_magnet_direction, resolve_material
from .models import DesignModel, NodeModel, TestModel
from .profiles import MaxwellProfile, get_profile

logger = logging.getLogger(__name__)


@dataclass
class MaxwellCommand:
    """A single recorded API call."""

    method: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class BuildResult:
    ok: bool
    mode: str
    commands: list[MaxwellCommand] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    live: bool = False  # True if commands were actually executed
    project_path: str | None = None  # Path to saved .aedt file (live mode only)


class MaxwellSessionBuilder:
    """Builds a Maxwell 2D or 3D session from DoSA design model."""

    def __init__(
        self,
        design: DesignModel,
        profile: MaxwellProfile,
        out_dir: Path,
        mode: str = "2d",
        non_graphical: bool = True,
        new_desktop: bool = True,
    ):
        self.design = design
        self.profile = profile
        self.out_dir = out_dir
        self.mode = mode
        self.non_graphical = non_graphical
        self.new_desktop = new_desktop
        self._commands: list[MaxwellCommand] = []
        self._errors: list[str] = []
        self._app: Any = None
        # Canonical .aedt path: <out_dir>/<design_name>.aedt
        self._project_file: str = str(
            (self.out_dir / f"{self.design.name or 'DoSA_Project'}.aedt").resolve()
        )

    def _record(self, method: str, **kwargs: Any) -> None:
        self._commands.append(MaxwellCommand(method=method, args=kwargs))

    def _try_get_app(self):
        """Instantiate a live Maxwell session.

        Follows the pyaedt-recommended pattern from project examples
        (e.g. Basic_Train_Day1bc.ipynb, MaxwellAedt.ipynb):
        - Pass full ``.aedt`` file path as ``project``
        - ``new_desktop=False`` so multiple sequential sessions reuse AEDT
        - ``close_on_exit=False`` so we control release explicitly
        - ``remove_lock=True`` to recover from a previous crashed session
        """
        # Ensure target directory exists before AEDT writes anything
        self.out_dir.mkdir(parents=True, exist_ok=True)

        try:
            if self.mode == "2d":
                from ansys.aedt.core import Maxwell2d  # type: ignore

                self._app = Maxwell2d(
                    project=self._project_file,
                    design=self.design.name or "DoSA_Design",
                    solution_type=self.profile.solution_type,
                    non_graphical=self.non_graphical,
                    new_desktop=self.new_desktop,
                    remove_lock=True,
                )
            else:
                from ansys.aedt.core import Maxwell3d  # type: ignore

                self._app = Maxwell3d(
                    project=self._project_file,
                    design=self.design.name or "DoSA_Design",
                    solution_type=self.profile.solution_type,
                    non_graphical=self.non_graphical,
                    new_desktop=self.new_desktop,
                    remove_lock=True,
                )

            # Set modeler units to mm (DoSA native unit)
            if self._app:
                self._app.modeler.model_units = "mm"

        except (ImportError, ModuleNotFoundError):
            self._app = None
            logger.info("PyAEDT not available. Running in script-log mode.")
        except Exception as exc:
            self._app = None
            self._errors.append(f"Maxwell session init failed: {exc}")

    # ─── Geometry ──────────────────────────────────────────────────────

    def _build_geometry(self) -> None:
        """Create all part geometries in Maxwell."""
        for part in self.design.parts:
            geom = self._extract_part_geometry(part)
            if geom is None or not geom.is_valid:
                self._errors.append(f"Geometry extraction failed for part '{part.name}'")
                continue

            if self._app is not None:
                self._create_live_geometry(geom)
            else:
                self._record_geometry(geom)

    def _extract_part_geometry(self, part: NodeModel) -> Geometry2D | None:
        """Extract geometry — prefer Shape block, fall back to coil params."""
        geom = extract_geometry(part)
        if geom is not None and geom.is_valid:
            return geom

        # Fallback for coils with design parameters
        if part.kind == "Coil":
            props = part.properties
            inner_d = float(props.get("InnerDiameter", 0))
            outer_d = float(props.get("OuterDiameter", 0))
            height = float(props.get("Height", 0))
            if inner_d > 0 and outer_d > 0 and height > 0:
                return geometry_from_coil_params(part.name, inner_d, outer_d, height)

        return geom

    def _create_live_geometry(self, geom: Geometry2D) -> None:
        """Create geometry in live Maxwell session.

        - In 2D mode: creates a closed sheet (covered polyline).
        - In 3D mode: creates the same sheet then revolves 360 around Y axis
          (DoSA is axisymmetric, X = radial, Y = axial).
        """
        pts = geom.to_polyline_points()
        self._record("modeler.create_polyline", name=geom.name, points=pts, close=True)
        if not self._app:
            return

        try:
            poly = self._app.modeler.create_polyline(
                points=pts,
                close_surface=True,
                cover_surface=True,
                name=geom.name,
            )
            if poly is None:
                self._errors.append(f"create_polyline returned None for '{geom.name}'")
                return
        except Exception as exc:
            self._errors.append(f"create_polyline failed for '{geom.name}': {exc}")
            return

        if self.mode == "3d":
            self._record("modeler.sweep_around_axis", name=geom.name, axis="Y", angle=360)
            try:
                self._app.modeler.sweep_around_axis(
                    assignment=geom.name,
                    axis="Y",
                    sweep_angle=360,
                )
            except Exception as exc:
                self._errors.append(f"sweep_around_axis failed for '{geom.name}': {exc}")

    def _record_geometry(self, geom: Geometry2D) -> None:
        """Record geometry command without execution."""
        pts = geom.to_polyline_points()
        self._record("modeler.create_polyline", name=geom.name, points=pts, close=True)

    # ─── Materials ─────────────────────────────────────────────────────

    def _assign_materials(self) -> None:
        """Assign materials to all parts."""
        for part in self.design.parts:
            mat_name = part.properties.get("Material", "")
            if not mat_name:
                continue

            try:
                mat_info = resolve_material(mat_name)
            except ValueError as e:
                self._errors.append(str(e))
                continue

            self._record(
                "assign_material",
                object_name=part.name,
                material=mat_info.maxwell_name,
            )

            if self._app:
                try:
                    self._app.assign_material(
                        assignment=[part.name],
                        material=mat_info.maxwell_name,
                    )
                except Exception as exc:
                    self._errors.append(
                        f"assign_material failed for '{part.name}' "
                        f"(material='{mat_info.maxwell_name}'): {exc}"
                    )

            # Magnet direction handling
            if part.kind == "Magnet":
                direction_str = part.properties.get("MagnetDirection", "UP")
                dx, dy = resolve_magnet_direction(direction_str)
                self._record(
                    "assign_magnet_direction",
                    object_name=part.name,
                    direction=(dx, dy),
                )

    # ─── Excitations ───────────────────────────────────────────────────

    def _assign_excitations(self) -> None:
        """Set up coil excitation (winding and current)."""
        for part in self.design.parts:
            if part.kind != "Coil":
                continue

            props = part.properties
            turns = int(props.get("Turns", 0))
            current_dir = props.get("CurrentDirection", "IN")
            polarity = "Positive" if current_dir == "IN" else "Negative"

            self._record(
                "assign_coil",
                object_name=part.name,
                conductors_number=turns,
                polarity=polarity,
            )

            if self._app:
                try:
                    # Newer pyaedt API uses 'assignment' / 'conductors_number'
                    self._app.assign_coil(
                        assignment=[part.name],
                        conductors_number=turns,
                        polarity=polarity,
                        name=f"Coil_{part.name}",
                    )
                except TypeError:
                    try:
                        # Legacy keyword fallback
                        self._app.assign_coil(
                            input_object=[part.name],
                            conductor_number=turns,
                            polarity=polarity,
                            name=f"Coil_{part.name}",
                        )
                    except Exception as exc:
                        self._errors.append(f"assign_coil failed for '{part.name}': {exc}")
                except Exception as exc:
                    self._errors.append(f"assign_coil failed for '{part.name}': {exc}")

    # ─── Boundary and Motion ───────────────────────────────────────────

    def _assign_motion(self) -> None:
        """Assign translate motion for moving parts (if Transient)."""
        if self.profile.solution_type != "Transient":
            return

        moving_parts = [
            p for p in self.design.parts if p.properties.get("MovingParts") == "MOVING"
        ]
        if not moving_parts:
            return

        band_names = [p.name for p in moving_parts]
        self._record(
            "assign_translate_motion",
            band_objects=band_names,
            axis="Y",
            positive_limit="5mm",
            negative_limit="5mm",
        )

        if self._app:
            try:
                self._app.assign_translate_motion(
                    assignment=band_names[0],
                    coordinate_system="Global",
                    axis="Y",
                    positive_limit="5mm",
                    negative_limit="5mm",
                )
            except TypeError:
                try:
                    self._app.assign_translate_motion(
                        band_object=band_names[0],
                        coordinate_system="Global",
                        axis="Y",
                        positive_limit="5mm",
                        negative_limit="5mm",
                    )
                except Exception as exc:
                    self._errors.append(f"assign_translate_motion failed: {exc}")
            except Exception as exc:
                self._errors.append(f"assign_translate_motion failed: {exc}")

    # ─── Analysis Setup ────────────────────────────────────────────────

    def _create_setup(self) -> None:
        """Create analysis setup based on profile."""
        setup_params: dict[str, Any] = {
            "name": "DoSA_Setup",
            "solution_type": self.profile.solution_type,
        }

        if self.profile.solution_type == "Transient":
            setup_params["time_step"] = self.profile.time_step
            setup_params["stop_time"] = self.profile.stop_time
        elif self.profile.solution_type == "Magnetostatic":
            setup_params["percent_refinement"] = 30
            setup_params["max_passes"] = 10

        self._record("create_setup", **setup_params)

        if self._app:
            try:
                if self.profile.solution_type == "Transient":
                    setup = self._app.create_setup(name="DoSA_Setup")
                    setup.props["StopTime"] = self.profile.stop_time
                    setup.props["TimeStep"] = self.profile.time_step
                else:
                    setup = self._app.create_setup(name="DoSA_Setup")
                    setup.props["PercentRefinement"] = 30
                    setup.props["MaximumPasses"] = 10
            except Exception as exc:
                self._errors.append(f"create_setup failed: {exc}")

    # ─── Force Assignment ──────────────────────────────────────────────

    def _assign_force(self) -> None:
        """Assign force calculation on moving parts."""
        moving_parts = [
            p for p in self.design.parts if p.properties.get("MovingParts") == "MOVING"
        ]
        for part in moving_parts:
            self._record("assign_force", object_name=part.name)
            if self._app:
                try:
                    self._app.assign_force(
                        assignment=part.name,
                        reference_cs_name="Global",
                        force_name=f"Force_{part.name}",
                    )
                except TypeError:
                    try:
                        self._app.assign_force(
                            input_object=part.name,
                            reference_cs="Global",
                            force_name=f"Force_{part.name}",
                        )
                    except Exception as exc:
                        self._errors.append(f"assign_force failed for '{part.name}': {exc}")
                except Exception as exc:
                    self._errors.append(f"assign_force failed for '{part.name}': {exc}")

    # ─── Test Scenario Mapping ─────────────────────────────────────────

    def _apply_test_conditions(self) -> None:
        """Apply voltage/current from first ForceTest to coil excitations."""
        force_tests = [t for t in self.design.tests if "FORCE" in t.kind.upper()]
        if not force_tests:
            return

        test = force_tests[0]
        voltage = float(test.properties.get("Voltage", 0))
        current = float(test.properties.get("Current", 0))

        # Find coils and set excitation value
        for part in self.design.parts:
            if part.kind != "Coil":
                continue

            resistance = float(part.properties.get("Resistance", 0))
            excitation_current = current if current > 0 else (voltage / resistance if resistance > 0 else 0)

            self._record(
                "assign_winding_current",
                coil_name=part.name,
                current_a=excitation_current,
                voltage_v=voltage,
            )

            if self._app:
                try:
                    self._app.assign_winding(
                        assignment=[f"Coil_{part.name}"],
                        winding_type="Current",
                        current=f"{excitation_current}A",
                        name=f"Winding_{part.name}",
                    )
                except TypeError:
                    try:
                        self._app.assign_winding(
                            coil_terminals=[f"Coil_{part.name}"],
                            winding_type="Current",
                            current_value=f"{excitation_current}A",
                            name=f"Winding_{part.name}",
                        )
                    except Exception as exc:
                        self._errors.append(f"assign_winding failed: {exc}")
                except Exception as exc:
                    self._errors.append(f"assign_winding failed: {exc}")

    # ─── Public interface ──────────────────────────────────────────────

    def build(self, live: bool = False) -> BuildResult:
        """Execute the full build pipeline.

        Args:
            live: If True, attempt to connect to a real Maxwell session.
                  If False (default), only record commands.
        """
        if live:
            self._try_get_app()

        self._build_geometry()
        self._assign_materials()
        # Setup must exist before motion (Maxwell requires Transient setup for motion)
        self._create_setup()
        self._assign_excitations()
        self._assign_motion()
        self._assign_force()
        self._apply_test_conditions()

        # Save command log
        self._save_command_log()

        # Persist .aedt project for live sessions, then release cleanly so the
        # next session can launch without 'Rename' / lock-file errors.
        # Pattern from pyaedt-examples (e.g. 2d_axi_magnetostatic_actuator.py,
        # lorentz_actuator.py, transient_winding.py): save_project() and
        # release_desktop() are called with NO arguments, followed by sleep(3).
        project_path: str | None = None
        if self._app is not None:
            try:
                self._app.save_project()
                project_path = (
                    getattr(self._app, "project_file", None) or self._project_file
                )
            except Exception as exc:
                self._errors.append(f"save_project failed: {exc}")
                project_path = self._project_file
            finally:
                try:
                    # Keep desktop alive so the next builder can reuse it
                    self._app.release_desktop(
                        close_projects=False, close_desktop=False
                    )
                except Exception:
                    pass

        return BuildResult(
            ok=len(self._errors) == 0,
            mode=self.mode,
            commands=list(self._commands),
            errors=list(self._errors),
            live=self._app is not None,
            project_path=project_path,
        )

    def _save_command_log(self) -> None:
        """Save the recorded commands to a JSON file."""
        self.out_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.out_dir / "maxwell_commands.json"
        payload = {
            "design_name": self.design.name,
            "mode": self.mode,
            "profile": asdict(self.profile),
            "commands": [asdict(cmd) for cmd in self._commands],
            "errors": self._errors,
        }
        log_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
