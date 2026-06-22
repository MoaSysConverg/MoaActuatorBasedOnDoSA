"""Writer for DoSA .dsa format — saves DesignModel back to disk.

Produces a simplified $begin/$end block format compatible with DoSA-2D parser.
"""

from __future__ import annotations

from pathlib import Path

from .models import DesignModel, NodeModel, TestModel


def write_dosa_file(design: DesignModel, path: str | Path) -> None:
    """Write a DesignModel to a .dsa or .dsa3d file."""
    path = Path(path)
    lines: list[str] = []

    lines.append(f'$begin "Design"')
    lines.append(f'  Name={design.name}')
    lines.append(f'  SourceType={design.source_type}')
    lines.append("")

    # Parts
    for part in design.parts:
        lines.append(f'  $begin "{part.kind}"')
        lines.append(f'    Name={part.name}')
        for key, value in part.properties.items():
            if key == "ShapePoints":
                _write_shape_points(lines, value)
            else:
                lines.append(f'    {key}={value}')

        # Write Shape child nodes (geometry from DoSA or AEDT)
        for child in part.children:
            if child.kind == "Shape":
                _write_shape_child(lines, child)

        lines.append(f'  $end "{part.kind}"')
        lines.append("")

    # Tests
    for test in design.tests:
        lines.append(f'  $begin "{test.kind}"')
        lines.append(f'    Name={test.name}')
        for key, value in test.properties.items():
            lines.append(f'    {key}={value}')
        lines.append(f'  $end "{test.kind}"')
        lines.append("")

    lines.append(f'$end "Design"')
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def _write_shape_points(lines: list[str], points: list) -> None:
    """Write shape points block from properties dict format."""
    lines.append(f'    $begin "Shape"')
    lines.append(f'      FaceType=Polygon')
    lines.append(f'      PointCount={len(points)}')
    for i, pt in enumerate(points):
        if isinstance(pt, dict):
            x, y = pt.get("x", 0), pt.get("y", 0)
        else:
            x, y = pt[0], pt[1]
        lines.append(f'      X{i}={x}')
        lines.append(f'      Y{i}={y}')
    lines.append(f'    $end "Shape"')


def _write_shape_child(lines: list[str], shape_node: NodeModel) -> None:
    """Write Shape child node using raw_lines (DoSA native format).

    raw_lines contain: BasePointX=, BasePointY=, FaceType=,
    and PointX=/PointY= pairs.
    """
    lines.append('    $begin "Shape"')
    if shape_node.raw_lines:
        for raw in shape_node.raw_lines:
            lines.append(f'      {raw}')
    else:
        # Fallback: write from properties
        props = shape_node.properties
        lines.append(
            f'      BasePointX={props.get("BasePointX", 0)}'
        )
        lines.append(
            f'      BasePointY={props.get("BasePointY", 0)}'
        )
        lines.append(
            f'      FaceType={props.get("FaceType", "POLYGON")}'
        )
        # Serialize point list if present in properties
        i = 0
        while f"X{i}" in props and f"Y{i}" in props:
            lines.append(f'      PointX={props[f"X{i}"]}')
            lines.append(f'      PointY={props[f"Y{i}"]}')
            lines.append('      LineKind=STRAIGHT')
            lines.append('      ArcDriction=FORWARD')
            i += 1
    lines.append('    $end "Shape"')
