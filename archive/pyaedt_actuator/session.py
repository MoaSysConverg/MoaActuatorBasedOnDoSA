from __future__ import annotations

import os
from typing import Optional

from .config import ActuatorPaths, MaxwellSettings


def _norm_path(path: Optional[str]) -> str:
    if not path:
        return ""
    return os.path.normcase(os.path.normpath(str(path)))


def _norm_solution(solution: str) -> str:
    return str(solution).strip().lower().replace(" ", "").replace("-", "")


def _is_axis_about_z(solution: str) -> bool:
    n = _norm_solution(solution)
    return n.endswith("z") or n.endswith("aboutz")


def _to_api_solution(solution: str) -> str:
    alias = {
        "magnetostaticz": "Magnetostatic",
        "magnetostatic2d": "Magnetostatic",
        "magnetostaticaboutz": "Magnetostatic",
        "transientz": "Transient",
        "transient2d": "Transient",
        "electrostaticz": "Electrostatic",
    }
    n = _norm_solution(solution)
    return alias.get(n, str(solution))


def ensure_project(paths: ActuatorPaths, settings: MaxwellSettings):
    """Connect Desktop, load/create project, and return Maxwell2d handle."""

    from ansys.aedt.core import Desktop, Maxwell2d

    fullfile_path = os.path.abspath(paths.project_file)
    project_exists = os.path.exists(fullfile_path)

    desktop = Desktop(
        version=settings.aedt_version,
        non_graphical=settings.non_graphical,
        new_desktop=False,
    )

    current_project = None
    try:
        project_path_attr = desktop.project_path
        if callable(project_path_attr):
            current_project = project_path_attr()
        else:
            current_project = project_path_attr
    except (AttributeError, TypeError):
        current_project = None

    current_project_norm = _norm_path(current_project)
    target_project_norm = _norm_path(fullfile_path)

    if project_exists:
        if current_project_norm != target_project_norm:
            desktop.load_project(fullfile_path)
    else:
        m2d = Maxwell2d(
            project=fullfile_path,
            design=paths.design_name,
            solution_type=settings.solution_type,
            version=settings.aedt_version,
            non_graphical=settings.non_graphical,
            new_desktop=False,
        )
        m2d.modeler.model_units = settings.model_units
        m2d.save_project(file_name=fullfile_path)

    m2d = Maxwell2d(
        project=fullfile_path,
        design=paths.design_name,
        version=settings.aedt_version,
        non_graphical=settings.non_graphical,
        new_desktop=False,
    )

    target_solution_raw = str(settings.solution_type)
    target_solution_api = _to_api_solution(target_solution_raw)
    use_about_z = _is_axis_about_z(target_solution_raw)
    current_solution = str(m2d.solution_type)

    if _norm_solution(current_solution) != _norm_solution(target_solution_api):
        if (
            use_about_z
            and _norm_solution(target_solution_api) == "magnetostatic"
        ):
            m2d.odesign.SetSolutionType("Magnetostatic", "about Z")
        else:
            try:
                m2d.odesign.SetSolutionType(target_solution_api)
            except TypeError:
                m2d.odesign.SetSolutionType(target_solution_api, "")

        m2d = Maxwell2d(
            project=fullfile_path,
            design=paths.design_name,
            version=settings.aedt_version,
            non_graphical=settings.non_graphical,
            new_desktop=False,
        )

    m2d.modeler.model_units = settings.model_units
    m2d.save_project(file_name=fullfile_path)

    return desktop, m2d


def ensure_transient_design(m2d, design_name: str = "02_Actuator_Transient"):
    """Duplicate current design and switch to transient solution."""

    if design_name not in m2d.design_list:
        m2d.duplicate_design(name=design_name)

    m2d.set_active_design(design_name)
    m2d.odesign.SetSolutionType("Transient", "about Z")
    return m2d
