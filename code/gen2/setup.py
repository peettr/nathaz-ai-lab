"""Physical settings for the supplied two-dimensional square-cylinder mesh.

The caller owns mesh import, initialization, report definitions and solution runs.
"""


def _node(root, path):
    for part in path.split("."):
        root = getattr(root, part)
    return root


def _set(root, paths, values):
    """Try known settings-API layouts; fail rather than silently use defaults."""
    errors = []
    for path in paths:
        for value in values:
            try:
                item = _node(root, path)
                item.set_state(value)
                return
            except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as exc:
                errors.append(f"{path}={value!r}: {exc}")
    raise RuntimeError("Could not set Fluent setting: " + "; ".join(errors))


def _constant(root, paths, number):
    _set(root, paths, (number, {"value": number},
                       {"option": "constant", "value": number}))


def configure(solver, case, model):
    if model != "sst":
        raise ValueError("Only the requested k-omega SST model is supported")
    u, rho, nu, d, dt = (float(case[x]) for x in ("u", "rho", "nu", "d", "dt"))
    if min(u, rho, nu, d, dt) <= 0:
        raise ValueError("u, rho, nu, d and dt must be positive")
    k = float(case.get("inlet_k", 1e-5))
    epsilon = float(case.get("inlet_epsilon", 1e-5))
    omega = epsilon / (float(case.get("c_mu", 0.09)) * k)
    span = float(case.get("span", 1.0))
    mu = rho * nu  # Fluent's material viscosity is DYNAMIC, not kinematic.

    _set(solver, ("setup.general.solver.time",), ("unsteady-2nd-order",))
    _set(solver, ("setup.models.viscous.model",), ("k-omega",))
    _set(solver, ("setup.models.viscous.k_omega_model",), ("sst",))
    _constant(solver, ("setup.materials.fluid.air.density.value",
                       "setup.materials.fluid.air.density"), rho)
    _constant(solver, ("setup.materials.fluid.air.viscosity.value",
                       "setup.materials.fluid.air.viscosity"), mu)

    inlet = solver.setup.boundary_conditions.velocity_inlet["inlet"]
    # A normal-to-boundary velocity is wrong on a semicircular inlet: +x
    # Cartesian components must be specified everywhere on that arc.
    try:
        _set(inlet, ("velocity_specification",),
             ("Components", "components"))
        _constant(inlet, ("x_velocity", "momentum.x_velocity"), u)
        _constant(inlet, ("y_velocity", "momentum.y_velocity"), 0.0)
    except RuntimeError:
        _set(inlet, ("momentum.velocity", "velocity"),
             ({"option": "components", "components": {"x": u, "y": 0.0}},))
    _set(inlet, ("turbulence_specification", "turbulence.specification"),
         ("K and Omega", "k-omega"))
    _constant(inlet, ("turbulent_kinetic_energy", "turbulence.turbulent_kinetic_energy"), k)
    _constant(inlet, ("specific_dissipation_rate", "turbulence.specific_dissipation_rate"), omega)

    outlet = solver.setup.boundary_conditions.pressure_outlet["outlet"]
    _constant(outlet, ("gauge_pressure", "momentum.gauge_pressure"), 0.0)
    # The cylinder is the existing stationary, no-slip wall zone in the mesh.
    solver.setup.boundary_conditions.wall["cylinder"]

    ref = solver.setup.reference_values
    _constant(ref, ("density",), rho)
    _constant(ref, ("velocity",), u)
    _constant(ref, ("length",), d)
    _constant(ref, ("area",), d * span)
    _constant(ref, ("depth",), span)
    _constant(solver, ("solution.run_calculation.time_step_size",
                       "solution.run_calculation.transient_controls.time_step_size"), dt)
    return {"omega": omega, "dynamic_viscosity": mu}
