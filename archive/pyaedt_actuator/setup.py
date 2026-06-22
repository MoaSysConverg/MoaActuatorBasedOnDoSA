from __future__ import annotations

from .config import SweepSettings


def create_magnetostatic_setup(m2d, setup_name: str = "MySetup"):
    setup = m2d.create_setup(setup_name)
    setup.props["MaximumPasses"] = 3
    setup.props["PercentRefinement"] = 30
    setup.props["PercentError"] = 0.1
    setup.props["MinimumPasses"] = 1
    setup.props["RelativeResidual"] = 1e-6
    setup.update()
    return setup


def add_parametric_sweep(m2d, sweep: SweepSettings):
    value_sweep = m2d.parametrics.add(
        sweep.amp_name,
        sweep.amp_start,
        sweep.amp_stop,
        sweep.amp_step,
        name=sweep.parametric_setup_name,
        variation_type="LinearStep",
    )
    value_sweep.add_variation(
        sweep.move_name,
        sweep.move_start,
        sweep.move_stop,
        sweep.move_step,
        variation_type="LinearStep",
    )
    return value_sweep


def run_parametric_sweep(value_sweep, cores: int = 8):
    value_sweep.analyze(cores=cores)


def assign_mesh_for_transient(m2d):
    band_mesh = m2d.mesh.assign_length_mesh(
        assignment="Band",
        inside_selection=True,
        maximum_length="0.1mm",
        maximum_elements=None,
        name="Band_Length",
    )

    steel_mesh = m2d.mesh.assign_length_mesh(
        assignment=["Housing", "Anchor"],
        inside_selection=True,
        maximum_length="1mm",
        maximum_elements=None,
        name="Steel_Length",
    )

    return {"band_mesh": band_mesh, "steel_mesh": steel_mesh}


def create_transient_setup(m2d, setup_name: str = "Transient_Setup1"):
    try:
        if setup_name in m2d.setup_names:
            m2d.delete_setup(setup_name)
    except RuntimeError:
        pass

    setup_tr = m2d.create_setup(name=setup_name)
    setup_tr.props["StopTime"] = "20ms"
    setup_tr.props["TimeStep"] = "0.2ms"
    setup_tr.props["NonlinearSolverResidual"] = "1e-6"
    setup_tr.update()

    setup_tr.set_save_fields(
        enable=True,
        range_type="Custom",
        subrange_type="LinearStep",
        start=0,
        stop=20,
        count=0.4,
        units="ms",
    )
    return setup_tr
