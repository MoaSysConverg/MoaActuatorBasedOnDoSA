from dataclasses import dataclass


@dataclass
class ActuatorPaths:
    """Filesystem inputs for AEDT project handling."""

    notebook_path: str
    project_name: str
    design_name: str = "01_Actuator"

    @property
    def project_file(self) -> str:
        import os

        return os.path.join(self.notebook_path, f"{self.project_name}.aedt")


@dataclass
class MaxwellSettings:
    """Runtime settings for Desktop/Maxwell sessions."""

    aedt_version: str = "2026.1"
    non_graphical: bool = False
    solution_type: str = "MagnetostaticZ"
    model_units: str = "mm"


@dataclass
class SweepSettings:
    """Basic parametric sweep settings used in the notebook workflow."""

    amp_name: str = "Amp_1"
    amp_start: int = 500
    amp_stop: int = 2000
    amp_step: int = 500
    move_name: str = "move"
    move_start: int = 0
    move_stop: int = 4
    move_step: int = 1
    parametric_setup_name: str = "ParametricSetup1"
