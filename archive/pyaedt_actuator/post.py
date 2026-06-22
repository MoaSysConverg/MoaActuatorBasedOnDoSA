from __future__ import annotations

import numpy as np


def create_force_report(m2d):
    return m2d.post.create_report(
        expressions=["Force.Force_z"],
        variations={"Amp_1": "All", "move": "All"},
        plot_name="Force Plot 1",
        primary_sweep_variable="move",
        plot_type="Rectangular Plot",
    )


def extract_force_surface_data(m2d, expr: str = "Force.Force_z"):
    rows = []
    amp_probe = m2d.post.get_solution_data(
        expressions=[expr],
        variations={"Amp_1": "All", "move": "All"},
        primary_sweep_variable="Amp_1",
    )
    if amp_probe is None:
        raise RuntimeError("Could not retrieve solution data.")

    amp_values_obj = getattr(amp_probe, "primary_sweep_values", None)
    amp_values_raw = list(amp_values_obj) if amp_values_obj is not None else []

    amp_values = []
    for value in amp_values_raw:
        s = str(value)
        if s not in amp_values:
            amp_values.append(s)

    if not amp_values:
        amp_values = ["500A", "1000A", "1500A", "2000A"]

    for amp in amp_values:
        sd = m2d.post.get_solution_data(
            expressions=[expr],
            variations={"Amp_1": amp, "move": "All"},
            primary_sweep_variable="move",
        )
        if sd is None:
            continue

        x_vals = np.array(sd.primary_sweep_values, dtype=float)
        y_vals = np.array(sd.data_real(expr), dtype=float)

        for x, y in zip(x_vals, y_vals):
            rows.append({"Amp_1": amp, "move": float(x), expr: float(y)})

    if not rows:
        raise RuntimeError("No variation results found for Amp_1/move.")

    return rows


def create_transient_field_plots(
    m2d,
    time_context: str = "0.02s",
    setup_name: str = "Transient_Setup1",
):
    setup_context = (
        f"{setup_name} : Transient"
        if setup_name in m2d.setup_names
        else None
    )
    intrinsics = {"Time": time_context}

    all_objects = [obj for obj in m2d.modeler.object_names if obj]
    if not all_objects:
        raise RuntimeError("No model objects found.")

    plot_requests = [
        ("Mesh", "Mesh_T20ms"),
        ("Flux_Lines", "FluxLines_T20ms"),
        ("Mag_B", "MagB_T20ms"),
    ]

    created_plots = {}
    for quantity, plot_name in plot_requests:
        field_plot = m2d.post.create_fieldplot_surface(
            assignment=all_objects,
            quantity=quantity,
            setup=setup_context,
            intrinsics=intrinsics,
            plot_name=plot_name,
        )
        created_plots[plot_name] = field_plot

    return created_plots
