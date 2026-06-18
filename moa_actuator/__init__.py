"""moa_actuator — Unified DoSA actuator design & simulation package.

Integrates DoSA-2D/3D file parsing, geometry, material mapping,
and multi-solver backends (Maxwell/FEMM/GetDP) with a PyQt6 GUI.
"""

from .models import DesignModel, NodeModel, TestModel
from .parser import parse_dosa_file
from .geometry import Geometry2D, extract_geometry, geometry_from_coil_params
from .mapping import resolve_material, resolve_magnet_direction, MaterialInfo

# dosa_maxwell is now a subpackage — re-export key API for convenience
from .dosa_maxwell import apply_dosa_to_maxwell, get_profile, list_profiles

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
    # dosa_maxwell bridge
    "apply_dosa_to_maxwell",
    "get_profile",
    "list_profiles",
]
