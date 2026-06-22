"""Post-processing utilities for actuator simulation results."""

from __future__ import annotations

import numpy as np


def create_force_report(m2d):
    """Create a Force vs displacement/current report."""
    return m2d.post.create_report(
        expressions=["Force.Force_z"],
        variations={"Amp_1": "All", "move": "All"},
        plot_name="Force Plot 1",
        primary_sweep_variable="move",
        plot_type="Rectangular Plot",
    )


def extract_force_surface_data(m2d, expr: str = "Force.Force_z"):
    """Extract force data across all parametric variations dynamically."""
    import logging
    logger = logging.getLogger(__name__)

    # 1. Resolve actual force expression from available quantities
    try:
        all_quantities = m2d.post.available_report_quantities()
        force_candidates = [q for q in all_quantities if "Force" in q and "Force_z" in q]
        if force_candidates:
            # Prefer ones containing plunger if plunger is in the name
            plunger_force = [q for q in force_candidates if "plunger" in q.lower()]
            if plunger_force:
                expr = plunger_force[0]
            else:
                expr = force_candidates[0]
    except Exception as e:
        logger.warning(f"Failed to query available report quantities: {e}")

    # 2. Resolve independent variables in the model
    independent_vars = []
    try:
        independent_vars = list(m2d.variable_manager.independent_variable_names)
    except Exception as e:
        logger.warning(f"Failed to query independent variables: {e}")

    amp_var = None
    move_var = None

    for var in independent_vars:
        if "amp" in var.lower():
            amp_var = var
        elif "move" in var.lower() or "stroke" in var.lower():
            move_var = var

    # Fallbacks if none identified
    if not amp_var:
        amp_candidates = [v for v in independent_vars if "amp" in v.lower()]
        if amp_candidates:
            amp_var = amp_candidates[0]
        elif independent_vars:
            amp_var = independent_vars[0]
        else:
            amp_var = "Amp_1"

    # Define variations dictionary dynamically based on what exists
    variations = {}
    if amp_var in independent_vars:
        variations[amp_var] = "All"
    if move_var and move_var in independent_vars:
        variations[move_var] = "All"

    # Get solution data probe using the amp variable
    amp_probe = m2d.post.get_solution_data(
        expressions=[expr],
        variations=variations,
        primary_sweep_variable=amp_var,
    )
    if amp_probe is None:
        # Fallback: try without variations filter
        amp_probe = m2d.post.get_solution_data(
            expressions=[expr],
        )
        if amp_probe is None:
            raise RuntimeError(f"Could not retrieve solution data for {expr}.")

    # Check if move_var is actually swept (has multiple values)
    is_move_swept = False
    if move_var and amp_probe.intrinsics and move_var in amp_probe.intrinsics:
        try:
            is_move_swept = len(amp_probe.intrinsics[move_var]) > 1
        except Exception:
            pass

    # Extract primary sweep values (Amp values)
    amp_values_obj = getattr(amp_probe, "primary_sweep_values", None)
    amp_values_raw = list(amp_values_obj) if amp_values_obj is not None else []

    amp_values = []
    for value in amp_values_raw:
        s = str(value)
        if s not in amp_values:
            amp_values.append(s)

    if not amp_values:
        amp_values = ["Default"]

    rows = []

    # 3. Fetch data points
    if is_move_swept and move_var:
        for amp in amp_values:
            current_vars = variations.copy()
            current_vars[amp_var] = amp
            sd = m2d.post.get_solution_data(
                expressions=[expr],
                variations=current_vars,
                primary_sweep_variable=move_var,
            )
            if sd is None:
                continue

            x_vals = np.array(sd.primary_sweep_values, dtype=float)
            y_vals = np.array(sd.data_real(expr), dtype=float)

            for x, y in zip(x_vals, y_vals):
                rows.append({amp_var: amp, move_var: float(x), expr: float(y)})
    else:
        # Only amp is swept (or move is constant)
        x_vals = np.array(amp_probe.primary_sweep_values, dtype=float)
        y_vals = np.array(amp_probe.data_real(expr), dtype=float)
        
        # Get constant move value if available
        const_move = 0.0
        if move_var and amp_probe.intrinsics and move_var in amp_probe.intrinsics:
            try:
                const_move = float(amp_probe.intrinsics[move_var][0])
            except Exception:
                pass
                
        for x, y in zip(x_vals, y_vals):
            rows.append({amp_var: str(x), "move": const_move, expr: float(y)})

    if not rows:
        raise RuntimeError(f"No variation results found for expression {expr}.")

    return rows


def create_transient_field_plots(
    m2d,
    time_context: str = "0.02s",
    setup_name: str = "Transient_Setup1",
):
    """Create field overlay plots for transient results."""
    intrinsics = {"Time": time_context}

    all_objects = [obj for obj in m2d.modeler.object_names if obj]
    if not all_objects:
        raise RuntimeError("No model objects found.")

    plot_requests = [
        ("Mesh", "Mesh_T20ms"),
        ("Flux_Lines", "FluxLines_T20ms"),
        ("Mag_B", "MagB_T20ms"),
    ]

    plots = {}
    for plot_type, plot_name in plot_requests:
        try:
            if plot_type == "Mesh":
                p = m2d.post.create_fieldplot_surface(
                    assignment=all_objects,
                    quantity="Mesh",
                    plot_name=plot_name,
                    intrinsics=intrinsics,
                )
            elif plot_type == "Flux_Lines":
                p = m2d.post.create_fieldplot_surface(
                    assignment=all_objects,
                    quantity="Flux_Lines",
                    plot_name=plot_name,
                    intrinsics=intrinsics,
                )
            else:
                p = m2d.post.create_fieldplot_surface(
                    assignment=all_objects,
                    quantity="Mag_B",
                    plot_name=plot_name,
                    intrinsics=intrinsics,
                )
            plots[plot_name] = p
        except Exception:
            pass

    return plots
