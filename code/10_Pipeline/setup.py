"""Candidate PyFluent solver configuration; requires live CRC job validation.

Fail closed on unavailable settings, zones or model toggles. No scientific result
can be asserted from this module until the resulting case and monitors are read.
"""


def configure(solver, case, model):
    s=solver.settings
    names={kind:set(getattr(s.setup.boundary_conditions,kind).get_object_names())
           for kind in ('velocity_inlet','pressure_outlet','wall')}
    expected={'velocity_inlet':{'inlet'},'pressure_outlet':{'outlet'},'wall':{'cylinder'}}
    for key,required in expected.items():
        if not required.issubset(names[key]):
            raise RuntimeError(f'missing {key}: expected {required}, found {names[key]}')
    visc=s.setup.models.viscous
    if model=='sst':
        visc.model='k-omega';visc.k_omega_model='sst'
    elif model=='k-epsilon-kl':
        visc.model='k-epsilon';visc.k_epsilon_model='standard'
        visc.options.production_kato_launder_enabled=True
        if not visc.options.production_kato_launder_enabled():
            raise RuntimeError('Kato-Launder option did not activate')
    else: raise ValueError(model)
    s.setup.general.solver.time='unsteady-2nd-order'
    # Air properties intentionally defined from dimensionless U=D=rho=1.
    air=s.setup.materials.fluid['air']
    air.density.value=case['rho']
    air.viscosity.value=case['rho']*case['nu']
    inlet=s.setup.boundary_conditions.velocity_inlet['inlet']
    # The upstream semicircle has varying normals. Magnitude/Normal would
    # produce a converging radial flow, not the uniform Cartesian free stream.
    inlet.momentum.velocity_specification_method = 'Components'
    inlet.momentum.velocity_components = [
        {'option': 'value', 'value': case['u']},
        {'option': 'value', 'value': 0.0},
    ]
    if model=='sst':
        inlet.turbulence.turbulence_specification='K and Omega'
        # epsilon = Cmu*k*omega, Cmu=0.09. Documented conversion.
        inlet.turbulence.turbulent_kinetic_energy=case['k_inlet']
        inlet.turbulence.specific_dissipation_rate=case['epsilon_inlet']/(.09*case['k_inlet'])
    else:
        inlet.turbulence.turbulence_specification='K and Epsilon'
        inlet.turbulence.turbulent_kinetic_energy=case['k_inlet']
        inlet.turbulence.turbulent_dissipation_rate=case['epsilon_inlet']
    s.setup.reference_values.area=case['d'] # 2D unit depth
    s.setup.reference_values.length=case['d']
    s.setup.reference_values.velocity=case['u']
    s.setup.reference_values.density=case['rho']
    s.setup.reference_values.viscosity=case['rho']*case['nu']
    s.setup.reference_values.depth=case['d']
    return names
