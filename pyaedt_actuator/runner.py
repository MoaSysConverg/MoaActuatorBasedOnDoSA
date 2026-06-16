from __future__ import annotations

from typing import Optional

from .config import ActuatorPaths, MaxwellSettings, SweepSettings
from .excitation import (
    assign_band_motion,
    assign_boundary_and_current,
    assign_force,
    replace_excitation_for_transient,
)
from .geometry import create_band_sheet, create_trc_geometry
from .post import (
    create_force_report,
    create_transient_field_plots,
    extract_force_surface_data,
)
from .session import ensure_project, ensure_transient_design
from .setup import (
    add_parametric_sweep,
    assign_mesh_for_transient,
    create_magnetostatic_setup,
    create_transient_setup,
    run_parametric_sweep,
)


class ActuatorSimulationRunner:
    """Notebook-to-package bridge for actuator Maxwell workflows."""

    def __init__(
        self,
        paths: ActuatorPaths,
        settings: MaxwellSettings,
        sweep: Optional[SweepSettings] = None,
    ):
        self.paths = paths
        self.settings = settings
        self.sweep = sweep or SweepSettings()
        self.desktop = None
        self.m2d = None

    def connect(self):
        self.desktop, self.m2d = ensure_project(self.paths, self.settings)
        return self.m2d

    def run_magnetostatic_pipeline(self, cores: int = 8):
        if self.m2d is None:
            self.connect()

        objects = create_trc_geometry(self.m2d)
        assign_boundary_and_current(self.m2d, coil_name=objects["coil"].name)
        assign_force(self.m2d, anchor_name=objects["anchor"].name)

        create_magnetostatic_setup(self.m2d, setup_name="MySetup")
        value_sweep = add_parametric_sweep(self.m2d, self.sweep)

        self.m2d.save_project()
        run_parametric_sweep(value_sweep, cores=cores)

        create_force_report(self.m2d)
        rows = extract_force_surface_data(self.m2d)
        return rows

    def run_transient_pipeline(self):
        if self.m2d is None:
            self.connect()

        ensure_transient_design(self.m2d, design_name="02_Actuator_Transient")
        create_band_sheet(self.m2d, name="Band")
        replace_excitation_for_transient(self.m2d)
        assign_band_motion(self.m2d)
        assign_mesh_for_transient(self.m2d)
        create_transient_setup(self.m2d, setup_name="Transient_Setup1")

        self.m2d.save_project()
        self.m2d.analyze_setup("Transient_Setup1")

        return create_transient_field_plots(
            self.m2d,
            time_context="0.02s",
            setup_name="Transient_Setup1",
        )
