"""B-H curve data parser for DoSA material files (.dmat).

Parses the DoSA_MS.dmat format and generates GetDP-compatible
B-H interpolation function blocks for nonlinear steel materials.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BHCurve:
    """B-H curve data for a single steel material."""

    name: str
    H: list[float] = field(default_factory=list)  # A/m
    B: list[float] = field(default_factory=list)  # T
    conductivity: float = 0.0

    @property
    def is_valid(self) -> bool:
        return len(self.H) >= 2 and len(self.H) == len(self.B)


def _find_dmat_file() -> Path | None:
    """Find the DoSA_MS.dmat file in known locations."""
    candidates = [
        Path(__file__).parent / "config" / "DoSA_MS.dmat",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def parse_dmat_file(file_path: str | Path | None = None) -> dict[str, BHCurve]:
    """Parse a DoSA .dmat material file into B-H curves.

    Parameters
    ----------
    file_path : path to .dmat file, or None to use bundled data.

    Returns
    -------
    dict mapping material name to BHCurve.
    """
    if file_path is None:
        file_path = _find_dmat_file()
        if file_path is None:
            return {}

    path = Path(file_path)
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8", errors="ignore")
    materials: dict[str, BHCurve] = {}

    # Parse $begin 'MaterialName' ... $end 'MaterialName' blocks
    # Note: .dmat uses single quotes, not double quotes
    mat_pattern = re.compile(
        r"\$begin\s+'([^']+)'\s*\n(.*?)\$end\s+'\1'",
        re.DOTALL,
    )

    for match in mat_pattern.finditer(text):
        name = match.group(1)
        body = match.group(2)

        if name == "MaterialDef":
            # Skip the outer wrapper block, recurse into its content
            for inner_match in mat_pattern.finditer(body):
                inner_name = inner_match.group(1)
                inner_body = inner_match.group(2)
                curve = _parse_material_body(inner_name, inner_body)
                if curve.is_valid:
                    materials[inner_name] = curve
        else:
            curve = _parse_material_body(name, body)
            if curve.is_valid:
                materials[name] = curve

    return materials


def _parse_material_body(name: str, body: str) -> BHCurve:
    """Parse the body of a material block."""
    curve = BHCurve(name=name)

    # Extract B-H coordinate pairs
    coord_pattern = re.compile(
        r"\$begin\s+'Coordinate'\s*\n(.*?)\$end\s+'Coordinate'",
        re.DOTALL,
    )
    for coord_match in coord_pattern.finditer(body):
        coord_body = coord_match.group(1)
        x_val = y_val = None
        for line in coord_body.splitlines():
            line = line.strip()
            if line.startswith("X="):
                x_val = float(line[2:])
            elif line.startswith("Y="):
                y_val = float(line[2:])
        if x_val is not None and y_val is not None:
            curve.H.append(x_val)
            curve.B.append(y_val)

    # Extract conductivity
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("conductivity="):
            try:
                curve.conductivity = float(line.split("=", 1)[1])
            except ValueError:
                pass

    return curve


def resolve_bh_curve(material_name: str, bh_curves: dict[str, BHCurve]) -> BHCurve | None:
    """Resolve a design material name to a BHCurve from the parsed dmat file."""
    if not bh_curves or not material_name:
        return None

    # 1. Try direct match
    name_clean = material_name.strip()
    if name_clean in bh_curves:
        return bh_curves[name_clean]

    # 2. Try normalized match (lowercase, spaces/hyphens to underscores)
    def normalize_name(n: str) -> str:
        return n.lower().replace(" ", "_").replace("-", "_")

    norm_target = normalize_name(name_clean)
    for name, curve in bh_curves.items():
        if normalize_name(name) == norm_target:
            return curve

    # 3. Try synonym mapping for Japanese/JIS equivalents or common steel designations
    synonyms = {
        "430_stainless_steel": "sus_430",
        "430stainlesssteel": "sus_430",
        "sus_430": "sus_430",
        "sus430": "sus_430",
        "416_stainless_steel": "sus_416",
        "416stainlesssteel": "sus_416",
        "sus_416": "sus_416",
        "sus416": "sus_416",
        "455_stainless_steel": "sus_455",
        "455stainlesssteel": "sus_455",
        "sus_455": "sus_455",
        "sus455": "sus_455",
    }
    
    norm_no_underscore = norm_target.replace("_", "")
    mapped_target = synonyms.get(norm_target) or synonyms.get(norm_no_underscore)
    if mapped_target:
        for name, curve in bh_curves.items():
            if normalize_name(name) == mapped_target:
                return curve

    # 4. Partial fallback match (e.g., if target is a substring or vice versa)
    for name, curve in bh_curves.items():
        name_norm = normalize_name(name)
        if norm_target in name_norm or name_norm in norm_target:
            return curve

    return None


def generate_bh_pro(materials: dict[str, BHCurve]) -> str:
    """Generate GetDP BH.pro content with B-H interpolation functions.

    Replicates DoSA-3D's BH.pro generation logic exactly.
    """
    lines = ["Function{", ""]

    for name, curve in materials.items():
        if not curve.is_valid:
            continue

        # B data array
        b_str = ", ".join(str(b) for b in curve.B)
        lines.append(f"    Mat_{name}_B() = {{")
        lines.append(f"    {b_str}}};")
        lines.append("")

        # H data array
        h_str = ", ".join(str(h) for h in curve.H)
        lines.append(f"    Mat_{name}_H() = {{")
        lines.append(f"    {h_str}}};")
        lines.append("")

        # Derived quantities (from DoSA-3D Scripts.cs m_str12_BH_Calulate_Script)
        lines.append(f"    Mat_{name}_B2() = Mat_{name}_B()^2;")
        lines.append(f"    Mat_{name}_nu() = Mat_{name}_H() / Mat_{name}_B();")
        lines.append(f"    Mat_{name}_nu(0) = Mat_{name}_nu(1);")
        lines.append("")
        lines.append(f"    Mat_{name}_nu_B2() = ListAlt[Mat_{name}_B2(), Mat_{name}_nu()];")
        lines.append(f"    nu_{name}[] = InterpolationLinear[SquNorm[$1]]{{ Mat_{name}_nu_B2() }};")
        lines.append(f"    dnudb2_{name}[] = dInterpolationLinear[SquNorm[$1]]{{ Mat_{name}_nu_B2() }};")
        lines.append(f"    H_{name}[] = nu_{name}[$1] * $1 ;")
        lines.append(f"    dhdb_{name}[] = TensorDiag[1,1,1] * nu_{name}[$1#1] + 2 * dnudb2_{name}[#1] * SquDyadicProduct[#1];")
        lines.append(f"    dhdb_{name}_NL[] = 2 * dnudb2_{name}[$1] * SquDyadicProduct[$1] ;")
        lines.append("")

    lines.append("}")
    return "\n".join(lines)


def write_dmat_file(file_path: str | Path | None = None, materials: dict[str, BHCurve] = None) -> None:
    """Write B-H curves to a DoSA .dmat material file."""
    if file_path is None:
        file_path = _find_dmat_file()
        if file_path is None:
            raise FileNotFoundError("Could not find DoSA_MS.dmat bundled file path.")

    if materials is None:
        materials = {}

    lines = []
    for name, curve in materials.items():
        lines.append("$begin 'MaterialDef'")
        lines.append(f"\t$begin '{name}'")
        lines.append("\t\t$begin 'BHCoordinates'")
        for h, b in zip(curve.H, curve.B):
            lines.append("\t\t\t$begin 'Coordinate'")
            h_str = str(int(h)) if h.is_integer() else str(h)
            b_str = str(int(b)) if b.is_integer() else str(b)
            lines.append(f"\t\t\t\tX={h_str}")
            lines.append(f"\t\t\t\tY={b_str}")
            lines.append("\t\t\t$end 'Coordinate'")
        lines.append("\t\t$end 'BHCoordinates'")
        cond_str = str(int(curve.conductivity)) if curve.conductivity.is_integer() else str(curve.conductivity)
        lines.append(f"\t\tconductivity={cond_str}")
        lines.append(f"\t$end '{name}'")
        lines.append("$end 'MaterialDef'")
        lines.append("")

    Path(file_path).write_text("\n".join(lines), encoding="utf-8")
