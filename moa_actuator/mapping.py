"""Material mapping from DoSA naming conventions to solver material names.

Supports Maxwell, FEMM, and GetDP material name resolution.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialInfo:
    maxwell_name: str
    category: str  # steel, magnet, conductor, air
    notes: str = ""


# Steel materials - DoSA name -> Maxwell library name
_STEEL_MAP: dict[str, MaterialInfo] = {
    "1010 steel": MaterialInfo("steel_1010", "steel", "Low carbon steel, common yoke/core"),
    "1020 steel": MaterialInfo("steel_1020", "steel"),
    "1008 steel": MaterialInfo("steel_1008", "steel"),
    "pure iron": MaterialInfo("iron", "steel", "High permeability pure iron"),
    "430 stainless steel": MaterialInfo("stainless_steel", "steel", "Ferritic stainless, plunger"),
    "416 stainless steel": MaterialInfo("stainless_steel", "steel"),
    "sus 430": MaterialInfo("stainless_steel", "steel", "Japanese standard equivalent"),
    "m-19": MaterialInfo("M19_29G", "steel", "Electrical steel"),
}

# Magnet materials - DoSA name -> Maxwell library name
_MAGNET_MAP: dict[str, MaterialInfo] = {
    "n30": MaterialInfo("NdFe30", "magnet"),
    "n33": MaterialInfo("NdFe33", "magnet"),
    "n35": MaterialInfo("NdFe35", "magnet"),
    "n38": MaterialInfo("NdFe38", "magnet"),
    "n40": MaterialInfo("NdFe40", "magnet"),
    "n42": MaterialInfo("NdFe42", "magnet"),
    "n45": MaterialInfo("NdFe45", "magnet"),
    "n48": MaterialInfo("NdFe48", "magnet"),
    "n50": MaterialInfo("NdFe50", "magnet"),
    "n52": MaterialInfo("NdFe52", "magnet"),
    "n55": MaterialInfo("NdFe55", "magnet"),
}

# Conductor materials
_CONDUCTOR_MAP: dict[str, MaterialInfo] = {
    "copper": MaterialInfo("copper", "conductor"),
    "aluminum": MaterialInfo("aluminum", "conductor"),
}

# Magnet direction to magnetization unit vector (for 2D axisymmetric)
MAGNET_DIRECTION_MAP: dict[str, tuple[float, float]] = {
    "UP": (0.0, 1.0),
    "DOWN": (0.0, -1.0),
    "LEFT": (-1.0, 0.0),
    "RIGHT": (1.0, 0.0),
}


def resolve_material(dosa_name: str) -> MaterialInfo:
    """Resolve a DoSA material name to solver material info.

    Raises ValueError if material is not found in any map.
    """
    key = dosa_name.strip().lower()

    if key in _STEEL_MAP:
        return _STEEL_MAP[key]
    if key in _MAGNET_MAP:
        return _MAGNET_MAP[key]
    if key in _CONDUCTOR_MAP:
        return _CONDUCTOR_MAP[key]
    if key == "air":
        return MaterialInfo("vacuum", "air")

    raise ValueError(
        f"Unknown material '{dosa_name}'. Add mapping to moa_actuator/mapping.py"
    )


def resolve_magnet_direction(direction_str: str) -> tuple[float, float]:
    """Return unit vector (x, y) for magnet polarization direction (2D)."""
    key = direction_str.strip().upper()
    if key not in MAGNET_DIRECTION_MAP:
        raise ValueError(f"Unknown magnet direction '{direction_str}'")
    return MAGNET_DIRECTION_MAP[key]


def resolve_magnet_direction_3d(
    rotation_axis: str, rotation_angle: float
) -> tuple[float, float, float]:
    """Return 3D magnetization unit vector from DoSA-3D rotation parameters.

    DoSA-3D defines magnet direction as a rotation from +Z axis
    around a specified axis (Y or Z) by a given angle.
    """
    import math

    angle_rad = math.radians(rotation_angle)
    axis = rotation_axis.strip().upper()

    if axis == "Y":
        # Rotation around Y: vector in XZ plane
        return (math.sin(angle_rad), 0.0, math.cos(angle_rad))
    elif axis == "Z":
        # Rotation around Z: vector in XY plane
        return (math.sin(angle_rad), math.cos(angle_rad), 0.0)
    else:
        # Default: +Z direction
        return (0.0, 0.0, 1.0)
