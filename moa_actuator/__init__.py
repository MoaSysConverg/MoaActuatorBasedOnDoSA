"""moa_actuator — Unified DoSA actuator design & simulation package.

Integrates DoSA-2D/3D file parsing, geometry, material mapping,
and multi-solver backends (Maxwell/FEMM/GetDP) with a PyQt6 GUI.
"""

from .models import DesignModel, NodeModel, TestModel
from .parser import parse_dosa_file
from .geometry import Geometry2D, extract_geometry, geometry_from_coil_params
from .mapping import resolve_material, resolve_magnet_direction, MaterialInfo

__all__ = [
    "DesignModel",
    "NodeModel",
    "TestModel",
    "parse_dosa_file",
    "Geometry2D",
    "extract_geometry",
    "geometry_from_coil_params",
    "resolve_material",
    "resolve_magnet_direction",
    "MaterialInfo",
]
