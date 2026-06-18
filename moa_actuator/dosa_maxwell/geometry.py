"""Geometry conversion from DoSA 2D Shape blocks to Maxwell 2D primitives.

DoSA 2D uses an axisymmetric coordinate system where:
- X axis = radial direction (always >= 0)
- Y axis = axial direction
- Shapes are polygons defined by ordered (X, Y) points in mm.

Maxwell 2D RZ (axisymmetric) uses the same convention:
- R = X (radial)
- Z = Y (axial)
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

    def to_polyline_points(self, unit_scale: float = 1.0) -> list[list[float]]:
        """Return ordered vertex list. Default keeps mm (DoSA native unit)."""
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
    """Parse point pairs from Shape block raw_lines.

    DoSA stores repeated PointX/PointY keys. We use raw_lines to read them
    in order, pairing consecutive PointX and PointY values.
    """
    points: list[Point2D] = []
    current_x: float | None = None

    for line in shape_node.raw_lines:
        stripped = line.strip()
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()

        if key == "PointX":
            current_x = float(value)
        elif key == "PointY":
            if current_x is not None:
                points.append(Point2D(current_x, float(value)))
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
