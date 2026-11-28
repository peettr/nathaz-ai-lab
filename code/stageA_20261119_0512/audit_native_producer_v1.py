#!/usr/bin/env python3
"""Fail-closed T17 v2 producer readiness audit; static only, never a GPU gate."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'stage/FluidX3D_on/src'
setup = (SRC / 'setup.cpp').read_text()
kernel = (SRC / 'kernel.cpp').read_text()
lbm = (SRC / 'lbm.cpp').read_text()
periodic = setup[setup.index('#ifdef PERIODIC_ABL_GROUND'):setup.index('#endif\n#ifdef WALL_GATE0')]
checks = {
    'setup_force_gate_still_present': 'T17 stage A prototype: native gate instrumentation not sealed' in periodic,
    'native_flags_uploaded_or_readback_in_periodic_setup': bool(re.search(r'(read_from_device|enqueue_read_from_device)', periodic)),
    'native_A1_mass_momentum_trace_in_periodic_setup': bool(re.search(r'(mass_trace|momentum_trace|Px_initial|Px_final)', periodic)),
    'native_A2_top_DDF_flux_export_in_periodic_setup': bool(re.search(r'(top_ddf_flux|top_momentum_exchange)', periodic)),
    'native_A7_ground_exchange_and_half_turnover_export_in_periodic_setup': bool(re.search(r'(half_turnover_windows|ground_exchange|F_ground_x)', periodic)),
    'periodic_macro_in_device_defines': 'PERIODIC_ABL_GROUND' in lbm,
    'top_specular_code_present': 'periodic_xyz.z==def_Nz-2u' in kernel,
}
dt = 1 / 78
T = 64 / 0.27810
out = {
    'scope': 'static source audit only; absence of names is not proof of absence of semantically equivalent instrumentation',
    'checks': checks,
    'turnover_s': T,
    'half_turnover_steps': T / (2 * dt),
    'A1_short_window_steps': 1000,
    'A7_note': 'A7 requires full T/2 windows; a 1000-step A1 smoke cannot supply even one such window at frozen dt.',
    'ready_for_gpu': False,
    'reason': 'protective abort still present; required native producer and half-turnover windows not yet demonstrated',
}
print(json.dumps(out, ensure_ascii=False, indent=2))
if not checks['setup_force_gate_still_present']:
    raise SystemExit('Unexpected removal of protective abort: inspect immediately')
