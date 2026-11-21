#!/usr/bin/env python3
"""Static T17 producer/units ledger and deliberate rejection fixtures; no solver run."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
src = root / 'stage/FluidX3D_on/src'
s = (src / 'setup.cpp').read_text()
k = (src / 'kernel.cpp').read_text()
l = (src / 'lbm.cpp').read_text()
u = (src / 'units.hpp').read_text()
branch = s[s.index('#ifdef PERIODIC_ABL_GROUND'):s.index('#endif\n#ifdef WALL_GATE0')]
checks = {
    'protected_no_run': 'T17 stage A prototype: native gate instrumentation not sealed' in branch,
    'force_density_interface': 'units.f(si_rho,f_si)' in branch and 'LBM lbm(256u,128u,66u,units.nu(1.48e-5f),f_lattice)' in branch,
    'force_density_units': 'float f(const float si_rho, const float si_g)' in u and 'float si_f(const float f)' in u,
    'host_flags_only': 'A3 host flags eligible=' in branch and 'read_from_device' not in branch,
    'periodic_device_macro': '#ifdef PERIODIC_ABL_GROUND' in l and '#define PERIODIC_ABL_GROUND' in l,
    'top_swaps_before_collision': 'fhn[10]=fhn[15]' in k and k.index('fhn[10]=fhn[15]', k.index('kernel void stream_collide')) < k.index('calculate_rho_u(fhn', k.index('kernel void stream_collide')),
    'wall_force_applied': 'fxn+=applied_ground_fx' in k,
    'tau_sum_is_kinematic_not_total_force': 'ground_tau_sum[xy+col]+=applied_ground_fx/rhon' in k,
    'existing_gate0_force_is_fixture_only': 'ground_force[n]=applied_ground_fx' in k and '#ifdef WALL_GATE0' in k,
    'no_periodic_native_trace': all(token not in branch for token in ('top_ddf_flux', 'half_turnover_windows', 'native_flag_eligibility', 'ground_exchange')),
}
assert all(checks.values()), checks
# A native evidence producer must be separately demonstrated; these are mandatory
# interface slots, not claims that source presently supplies them.
required = ('flags_device_readback', 'DDF_before_after_top_links',
            'ground_bounce_impulse', 'mirror_residual_impulse',
            'mass_and_Px_step_axis', 'signed_SI_conversion',
            'A7_half_turnover_step_boundaries')
def ready(fields):
    return all(fields.get(x) is True for x in required)
assert ready(dict.fromkeys(required, True))
for missing in required:
    f = dict.fromkeys(required, True)
    f[missing] = False
    assert not ready(f), missing
out = {
    'scope': 'STATIC ONLY; not a native gate or solver measurement',
    'checks': checks,
    'producer_slots_missing_or_unproven': list(required),
    'negative_fixtures': {x: 'REJECT' for x in required},
    'units': {
      'setup': 'si_rho=1 kg/m^3; f_si=u_star^2/H m/s^2; units.f(si_rho,f_si) supplies lattice force per volume',
      'A7': 'Px in kg m/s, dPx/dt and all three source/boundary terms in N; positive ground/top terms remove +x momentum',
      'tau_sum': 'kernel ground_tau_sum[xy+col] stores applied_ground_fx/rhon in lattice kinematic units; cannot replace total ground exchange',
      'top': 'record before/after mirrored DDF links for both parities, reconstruct physical populations; macro velocity gradient alone is not DDF momentum flux',
      'time': 'step 0 and each step for A1; A7 windows must span T/2=H/(2u*) using dt=units.si_t(1), not A1 1000 steps',
    },
    'ready_for_gpu': False,
}
print(json.dumps(out, ensure_ascii=False, indent=2))
