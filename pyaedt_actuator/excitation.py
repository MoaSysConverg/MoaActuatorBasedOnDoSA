from __future__ import annotations


def assign_boundary_and_current(m2d, coil_name: str = "Coil"):
    """Assign region vector potential and magnetostatic current."""

    region = m2d.modeler.create_region(pad_percent=100)
    region.material_name = "vacuum"
    m2d.assign_vector_potential(
        assignment=region.edges,
        boundary="VectorPotential1",
    )

    m2d["Amp_1"] = "1000A"
    m2d.assign_current(
        assignment=coil_name,
        amplitude="Amp_1",
        name="Current1",
    )

    return region


def assign_force(m2d, anchor_name: str = "Anchor"):
    return m2d.assign_force(assignment=anchor_name, force_name="Force")


def replace_excitation_for_transient(m2d):
    """Delete Current1, enable eddy effects, assign coil and winding."""

    excitation_name = "Current1"
    deleted_excitation = False

    for bnd in list(m2d.boundaries):
        if getattr(bnd, "name", "") == excitation_name:
            bnd.delete()
            deleted_excitation = True
            break

    if not deleted_excitation:
        try:
            m2d.oboundary.DeleteBoundaries([excitation_name])
        except RuntimeError:
            pass

    m2d.eddy_effects_on(
        assignment=["Housing", "Anchor"],
        enable_eddy_effects=True,
        enable_displacement_current=True,
    )

    coil_exc = m2d.assign_coil(
        assignment="Coil",
        conductors_number=500,
        polarity="Positive",
        name="Coil_500_Positive",
    )

    winding = m2d.assign_winding(
        assignment=None,
        winding_type="Voltage",
        is_solid=False,
        resistance=2,
        voltage=10,
        name="Winding1",
        current=0,
    )

    m2d.add_winding_coils(assignment=winding.name, coils=[coil_exc.name])

    return {"coil_excitation": coil_exc, "winding": winding}


def assign_band_motion(m2d, motion_name: str = "BandMotion1"):
    """Assign translational motion with mechanical transient properties."""

    if "Band" not in m2d.modeler.object_names:
        raise RuntimeError("Band object is required before assigning motion.")

    for bnd in list(m2d.boundaries):
        if getattr(bnd, "name", "") == motion_name:
            try:
                bnd.delete()
            except RuntimeError:
                pass

    load_force_candidates = [
        "-1000*Position-1",
        "-1000*Position-1newton",
        "(-1000*Position-1)*newton",
    ]

    last_error = None
    for lf in load_force_candidates:
        try:
            return m2d.assign_translate_motion(
                assignment="Band",
                coordinate_system="Global",
                axis="Z",
                positive_movement=False,
                start_position="0mm",
                periodic_translate=False,
                negative_limit="0mm",
                positive_limit="4.9mm",
                mechanical_transient=True,
                velocity=0,
                mass="0.001kg",
                damping=0,
                load_force=lf,
                motion_name=motion_name,
            )
        except RuntimeError as exc:
            last_error = exc

    raise RuntimeError(f"Failed to assign band motion: {last_error}")
