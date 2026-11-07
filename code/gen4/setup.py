"""Physical settings for the supplied two-dimensional square-cylinder mesh.

Only the PyFluent settings API is used. The caller owns the solver session,
mesh, report definitions, initialization and calculation.
"""


def _assign(root, paths, values):
    """Set the first supported settings leaf; fail rather than silently default."""
    errors = []
    for path in paths:
        try:
            parent = root
            parts = path.split(".")
            for part in parts[:-1]:
                parent = getattr(parent, part)
            leaf = parts[-1]
            for value in values:
                try:
                    setattr(parent, leaf, value)
                    return
                except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                    errors.append(f"{path}: {exc}")
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            errors.append(f"{path}: {exc}")
    raise RuntimeError("Could not configure any of " + repr(paths) + "; " + "; ".join(errors))


def _constant(value):
    return ({"option": "constant", "value": value}, {"value": value}, value)


def configure(solver, case, model):
    if model != "sst":
        raise ValueError("This case requires the k-omega SST model")
    u = float(case["u"])
    rho = float(case["rho"])
    nu = float(case["nu"])
    d = float(case["d"])
    dt = float(case["dt"])
    span = float(case.get("span", 1.0))
    k = float(case.get("inlet_k", 1e-5))
    epsilon = float(case.get("inlet_epsilon", 1e-5))
    c_mu = float(case.get("c_mu", 0.09))
    if min(u, rho, nu, d, dt, span, k, epsilon, c_mu) <= 0:
        raise ValueError("Physical parameters must be positive")
    mu = rho * nu
    omega = epsilon / (c_mu * k)  # omega [1/s] from epsilon = C_mu k omega

    _assign(solver, ["setup.general.solver.time"], ["unsteady-2nd-order"])
    viscous = solver.setup.models.viscous
    _assign(viscous, ["model"], ["k-omega"])
    _assign(viscous, ["k_omega_model", "kw_model", "kw_sst"],
            ["sst", "SST", True])

    air = solver.setup.materials.fluid["air"]
    _assign(air, ["density"], _constant(rho))
    _assign(air, ["viscosity"], _constant(mu))

    inlet = solver.setup.boundary_conditions.velocity_inlet["inlet"]
    _assign(inlet, ["velocity_specification_method", "velocity_spec"],
            ["Components", "components"])
    _assign(inlet, ["x_velocity", "x_vel"], _constant(u))
    _assign(inlet, ["y_velocity", "y_vel"], _constant(0.0))
    _assign(inlet, ["turbulence_specification", "turbulence_specification_method"],
            ["K and Omega", "k-omega", "k-and-omega"])
    _assign(inlet, ["turb_kinetic_energy", "turbulent_kinetic_energy", "turbulence_kinetic_energy"],
            _constant(k))
    _assign(inlet, ["spec_dissipation_rate", "specific_dissipation_rate", "omega"],
            _constant(omega))

    outlet = solver.setup.boundary_conditions.pressure_outlet["outlet"]
    _assign(outlet, ["gauge_pressure"], _constant(0.0))
    # The supplied cylinder zone is a wall; its default stationary no-slip
    # condition is retained. No wall motion or slip is introduced.
    solver.setup.boundary_conditions.wall["cylinder"]

    _assign(solver, ["solution.run_calculation.time_step_size",
                     "solution.run_calculation.time_step"], [dt])
    # For a two-dimensional calculation, frontal reference area = D * depth.
    ref = solver.setup.reference_values
    _assign(ref, ["area"], [d * span])
    _assign(ref, ["length"], [d])
    _assign(ref, ["density"], [rho])
    _assign(ref, ["velocity"], [u])
    _assign(ref, ["depth"], [span])
    return {"mu": mu, "inlet_omega": omega}
