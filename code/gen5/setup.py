"""Physical settings for the supplied 2-D square-cylinder mesh (PyFluent settings API)."""


def configure(solver, case, model):
    """Configure the existing mesh; do not initialize, solve, or create reports."""
    if model != "sst":
        raise ValueError("Only the prescribed k-omega SST model is supported")

    u = float(case["u"])
    rho = float(case["rho"])
    nu = float(case["nu"])
    d = float(case["d"])
    dt = float(case["dt"])
    span = float(case.get("span", 1.0))
    k = float(case.get("inlet_k", 1e-5))
    epsilon = float(case.get("inlet_epsilon", 1e-5))
    mu = rho * nu
    # Standard k-epsilon conversion at the inlet: epsilon = C_mu*k*omega.
    omega = epsilon / (0.09 * k)

    solver.setup.general.solver.time = "unsteady-2nd-order"
    solver.setup.models.viscous.model = "k-omega"
    solver.setup.models.viscous.k_omega_model = "sst"

    air = solver.setup.materials.fluid["air"]
    air.density.value = rho
    air.viscosity.value = mu

    inlet = solver.setup.boundary_conditions.velocity_inlet["inlet"]
    inlet.momentum.velocity_specification_method = "Components"
    inlet.momentum.x_velocity.value = u
    inlet.momentum.y_velocity.value = 0.0
    inlet.turbulence.turbulence_specification = "K and Omega"
    inlet.turbulence.turbulent_kinetic_energy.value = k
    inlet.turbulence.specific_dissipation_rate.value = omega

    outlet = solver.setup.boundary_conditions.pressure_outlet["outlet"]
    outlet.momentum.gauge_pressure.value = 0.0
    # The supplied cylinder wall retains its wall/no-slip default.

    ref = solver.setup.reference_values
    ref.density = rho
    ref.velocity = u
    ref.length = d
    ref.area = d * span
    ref.viscosity = mu
    # A planar 2-D mesh uses unit span; its force-coefficient reference area
    # is D times that span (1 m^2 here).

    solver.solution.run_calculation.time_step_size = dt
    return {"dynamic_viscosity": mu, "inlet_omega": omega}
