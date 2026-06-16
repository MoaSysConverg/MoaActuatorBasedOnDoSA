from __future__ import annotations


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

    return {
        "coil": coil,
        "anchor": anchor,
        "housing": housing,
    }


def create_band_sheet(m2d, name: str = "Band"):
    """Create band sheet using GUI-equivalent rectangle input."""

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
