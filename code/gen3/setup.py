"""Physical setup for the supplied two-dimensional square-cylinder mesh.

The caller owns mesh loading, report definitions, and execution.
"""


def configure(solver, case, model):
    """Configure SST, material, boundary conditions, transient time and references."""
    if model != "sst":
        raise ValueError("Only the 'sst' model is specified for this case")

    u = float(case["u"])
    rho = float(case["rho"])
    nu = float(case["nu"])
    d = float(case["d"])
    dt = float(case["dt"])
    span = float(case.get("span", 1.0))
    mu = rho * nu
    k = float(case.get("k", 1e-5))
    epsilon = float(case.get("epsilon", 1e-5))
    cmu = float(case.get("cmu", 0.09))
    omega = epsilon / (cmu * k)

    solver.setup.general.solver.time = "unsteady-2nd-order"
    solver.setup.models.viscous.model = "k-omega"
    solver.setup.models.viscous.k_omega_model = "sst"

    air = solver.setup.materials.fluid["air"]
    air.density.option = "constant"
    air.density.value = rho
    air.viscosity.option = "constant"
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
    # The supplied cylinder is a wall; its stationary no-slip default is retained.

    solver.solution.run_calculation.time_step_size = dt

    ref = solver.setup.reference_values
    ref.area = d * span
    ref.length = d
    ref.density = rho
    ref.velocity = u
    ref.viscosity = mu
    return {"mu": mu, "omega": omega, "reference_area": d * span}
