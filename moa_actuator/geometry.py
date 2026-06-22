"""Geometry extraction and construction for DoSA 2D/3D designs.

Handles:
- 2D polygon extraction from DoSA Shape blocks
- Coil rectangle construction from parameters
- 3D revolve support (2D section → Y-axis 360° rotation)
- Band sheet creation for transient analysis
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import NodeModel


@dataclass
class Point2D:
    x: float
    y: float


@dataclass
class Geometry2D:
    """A closed polygon representing a DoSA part cross-section."""

    name: str
    points: list[Point2D] = field(default_factory=list)
    face_type: str = "POLYGON"
    base_point: Point2D = field(default_factory=lambda: Point2D(0.0, 0.0))

    @property
    def is_valid(self) -> bool:
        return len(self.points) >= 3

    @property
    def min_x(self) -> float:
        return min(p.x for p in self.points) if self.points else 0.0

    @property
    def max_x(self) -> float:
        return max(p.x for p in self.points) if self.points else 0.0

    @property
    def min_y(self) -> float:
        return min(p.y for p in self.points) if self.points else 0.0

    @property
    def max_y(self) -> float:
        return max(p.y for p in self.points) if self.points else 0.0

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    def to_polyline_points(self, unit_scale: float = 1.0, plane: str = "XY") -> list[list[float]]:
        """Return ordered vertex list for Maxwell polyline creation.

        Args:
            unit_scale: Scaling factor (e.g. 1e-3 for mm→m).
            plane: Coordinate plane.
                - "XY": [R, Z, 0]  (default, for 3D or non-axisymmetric)
                - "XZ": [R, 0, Z]  (for Maxwell 2D axisymmetric about Z)
        """
        if plane.upper() == "XZ":
            return [[p.x * unit_scale, 0.0, p.y * unit_scale] for p in self.points]
        return [[p.x * unit_scale, p.y * unit_scale, 0.0] for p in self.points]


def extract_geometry(node: NodeModel) -> Geometry2D | None:
    """Extract 2D geometry from a DoSA part node's Shape child block."""
    shape_node = _find_shape_child(node)
    if shape_node is None:
        return None

    props = shape_node.properties
    base_x = float(props.get("BasePointX", 0))
    base_y = float(props.get("BasePointY", 0))
    face_type = props.get("FaceType", "POLYGON")

    points = _parse_points_from_shape(shape_node)
    if not points:
        return None

    return Geometry2D(
        name=node.name,
        points=points,
        face_type=face_type,
        base_point=Point2D(base_x, base_y),
    )


def _find_shape_child(node: NodeModel) -> NodeModel | None:
    for child in node.children:
        if child.kind == "Shape":
            return child
    return None


def _parse_points_from_shape(shape_node: NodeModel) -> list[Point2D]:
    """Parse point pairs from Shape block raw_lines (PointX/PointY pairs, or X{i}/Y{i} keys)."""
    points: list[Point2D] = []

    # 1. Try parsing from properties (X0, Y0, X1, Y1 format)
    props = shape_node.properties
    i = 0
    while f"X{i}" in props and f"Y{i}" in props:
        try:
            points.append(Point2D(float(props[f"X{i}"]), float(props[f"Y{i}"])))
        except ValueError:
            pass
        i += 1
    if points:
        return points

    # 2. Try parsing from raw_lines (PointX=, PointY= format)
    current_x: float | None = None
    for line in shape_node.raw_lines:
        stripped = line.strip()
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()

        if key == "PointX":
            try:
                current_x = float(value)
            except ValueError:
                pass
        elif key == "PointY":
            if current_x is not None:
                try:
                    points.append(Point2D(current_x, float(value)))
                except ValueError:
                    pass
                current_x = None

    return points


def geometry_from_coil_params(
    name: str,
    inner_diameter: float,
    outer_diameter: float,
    height: float,
    base_y: float = 0.0,
) -> Geometry2D:
    """Construct coil cross-section rectangle from coil design parameters (mm)."""
    r_inner = inner_diameter / 2.0
    r_outer = outer_diameter / 2.0
    y_bottom = base_y
    y_top = base_y + height

    points = [
        Point2D(r_inner, y_bottom),
        Point2D(r_outer, y_bottom),
        Point2D(r_outer, y_top),
        Point2D(r_inner, y_top),
    ]
    return Geometry2D(name=name, points=points, face_type="RECTANGLE")


def geometry_from_polygon_points(
    name: str, xy_pairs: list[tuple[float, float]]
) -> Geometry2D:
    """Construct geometry from explicit (x, y) coordinate pairs (mm)."""
    points = [Point2D(x, y) for x, y in xy_pairs]
    return Geometry2D(name=name, points=points, face_type="POLYGON")


def create_trc_geometry(m2d):
    """Create Coil, Anchor, Housing geometry from TRC tutorial dimensions."""

    m2d["move"] = "0mm"

    coil = m2d.modeler.create_rectangle(
        origin=["3mm", "0mm", "7mm"],
        sizes=[-14, 6],
        name="Coil",
        material="Copper",
    )

    anchor = m2d.modeler.create_rectangle(
        origin=["0mm", "0mm", "13mm - move"],
        sizes=[-8, 2],
        name="Anchor",
        material="steel_1008",
    )

    points_housing = [
        [0, 0, 0],
        [0, 0, -10],
        [12, 0, -10],
        [12, 0, 10],
        [2.5, 0, 10],
        [2.5, 0, 8],
        [10, 0, 8],
        [10, 0, -8],
        [2, 0, -8],
        [2, 0, 0],
    ]

    housing = m2d.modeler.create_polyline(
        points_housing,
        close_surface=True,
        name="Housing",
        material="steel_1008",
    )
    m2d.modeler.cover_lines(housing)

    return {"coil": coil, "anchor": anchor, "housing": housing}


def create_band_sheet(m2d, name: str = "Band"):
    """Create band sheet for transient motion analysis."""

    if name in m2d.modeler.object_names:
        m2d.modeler.delete(name)

    band = m2d.modeler.create_rectangle(
        origin=["0mm", "0mm", "15mm"],
        sizes=["-15mm", "2.5mm"],
        name=name,
        material="vacuum",
    )
    band.color = (173, 216, 230)
    band.transparency = 0.8
    return band
