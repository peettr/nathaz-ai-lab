"""Physical settings for the supplied 2-D square-cylinder Fluent mesh.

The caller owns mesh import, initialization, reports, and calculation.
"""


def configure(solver, case, model):
    """Configure the already-meshed PyFluent Solver settings session."""
    if model != "sst":
        raise ValueError("This configuration requires model='sst'.")

    u = float(case["u"])
    rho = float(case["rho"])
    nu = float(case["nu"])
    d = float(case["d"])
    dt = float(case["dt"])
    k = float(case["k"])
    epsilon = float(case["epsilon"])
    c_mu = float(case["c_mu"])
    depth = float(case["depth"])
    omega = epsilon / (c_mu * k)

    # SST is a k-omega model. Use second-order implicit transient time stepping.
    solver.setup.general.solver.time = "unsteady-2nd-order"
    solver.setup.models.viscous.model = "k-omega"
    solver.setup.models.viscous.k_omega_model = "sst"
    solver.solution.run_calculation.time_step_size = dt

    # Fluent material viscosity is dynamic (mu), not kinematic (nu).
    air = solver.setup.materials.fluid["air"]
    air.density.value = rho
    air.viscosity.value = rho * nu

    inlet = solver.setup.boundary_conditions.velocity_inlet["inlet"]
    inlet.momentum.velocity_specification_method = "Components"
    inlet.momentum.x_velocity.value = u
    inlet.momentum.y_velocity.value = 0.0
    inlet.turbulence.turbulence_specification = "K and Omega"
    inlet.turbulence.turbulent_kinetic_energy.value = k
    inlet.turbulence.specific_dissipation_rate.value = omega

    outlet = solver.setup.boundary_conditions.pressure_outlet["outlet"]
    outlet.momentum.gauge_pressure.value = 0.0
    # The supplied cylinder wall remains the default stationary no-slip wall.

    # In 2-D the reference area for force coefficients is D times unit depth.
    ref = solver.setup.reference_values
    ref.area = d * depth
    ref.length = d
    ref.depth = depth
    ref.density = rho
    ref.velocity = u
    return {"omega": omega, "dynamic_viscosity": rho * nu}
