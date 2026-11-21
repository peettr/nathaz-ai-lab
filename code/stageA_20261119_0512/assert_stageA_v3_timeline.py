#!/usr/bin/env python3
"""Fail-closed T17-v2 native ledger validator; synthetic fixtures are NOT device evidence."""
import argparse
import copy
import json
import math
from pathlib import Path
from assert_stageA_v2 import check as old_check

NX, NY, H = 256, 128, 64
AREA = NX * NY
DT = 1 / 78
HALF_T_STEPS = H / (2 * .27810 * DT)
REQUIRED_SOURCES = {'flags_device_readback', 'DDF_before_after_top_links',
                    'ground_bounce_impulse', 'mirror_residual_impulse',
                    'mass_and_Px_step_axis', 'signed_SI_conversion'}


def number(x, label):
    if isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x):
        raise ValueError(f'{label}: finite numeric value required')
    return float(x)


def validate(p):
    # Provenance strings alone never prove native execution; require producer hashes,
    # but still cross-check raw evidence and solver log externally before acceptance.
    sources = p.get('producer_sha256', {})
    if set(sources) != REQUIRED_SOURCES or any(not isinstance(v, str) or
            len(v) != 64 or any(c not in '0123456789abcdef' for c in v)
            for v in sources.values()):
        raise ValueError('missing/invalid native producer sha256 manifest')
    for name, case in p['cases'].items():
        if len(case.get('mass_trace', [])) != 1001:
            raise ValueError(f'{name}: A1 mass must include all 0..1000 steps')
        for i, row in enumerate(case['mass_trace']):
            if row['step'] != i: raise ValueError(f'{name}: mass step axis {i}')
            number(row['mass_kg'], f'{name}.mass[{i}]')
        case['mass'] = [case['mass_trace'][0]['mass_kg'],
                        case['mass_trace'][-1]['mass_kg']]
        windows = case['half_turnover_windows']
        if not windows: raise ValueError(f'{name}: missing A7 windows')
        previous = None
        for w in windows:
            a, b = w['step_start'], w['step_end']
            if not isinstance(a, int) or isinstance(a, bool) or not isinstance(b, int) or isinstance(b, bool):
                raise ValueError(f'{name}: integer window steps required')
            if a < 0 or b <= a or (previous is not None and a != previous):
                raise ValueError(f'{name}: invalid or nonconsecutive A7 windows')
            if abs((b-a)-HALF_T_STEPS) > 1:
                raise ValueError(f'{name}: A7 window must span T/2, not 1000 steps')
            previous = b
            if abs(number(w['dt_s'], 'dt_s') - (b-a)*DT) > 1e-6:
                raise ValueError(f'{name}: A7 physical time mismatch')
            parts = w['ground_components_N']
            if set(parts) != {'bounce', 'model', 'mirror_residual'}:
                raise ValueError(f'{name}: incomplete ground force ledger')
            summed = sum(number(parts[k], k) for k in parts)
            if abs(summed - number(w['F_ground_x'], 'F_ground_x')) > 1e-9 * max(1., abs(summed)):
                raise ValueError(f'{name}: ground components do not sum')
            if abs(number(w['F_top_x'], 'F_top_x') - number(w['top_DDF_N'], 'top_DDF_N')) > 1e-9 * max(1., abs(w['top_DDF_N'])):
                raise ValueError(f'{name}: top DDF impulse mismatch')
    b = p['no_force_double_mirror']
    if len(b.get('px_trace', [])) != 1001: raise ValueError('A1b full 0..1000 step axis required')
    for i, row in enumerate(b['px_trace']):
        if row['step'] != i: raise ValueError(f'A1b Px step {i}')
        number(row['Px_kg_m_s'], f'A1b.Px[{i}]')
    b['Px'] = [b['px_trace'][0]['Px_kg_m_s'], b['px_trace'][-1]['Px_kg_m_s']]
    return old_check(p)


def fixture():
    steps = round(HALF_T_STEPS)
    dt = steps * DT
    drive = .001 * H * AREA
    w = dict(step_start=0, step_end=steps, dt_s=dt, Px_initial=1.,
             Px_final=1.+dt*drive, F_ground_x=0., F_top_x=0., top_DDF_N=0.,
             ground_components_N={'bounce':0., 'model':0., 'mirror_residual':0.})
    c = dict(steps=1000, rho=1., F=.001, top_ddf_flux=0.,
             native_flag_eligibility=[True]*AREA, half_turnover_windows=[w],
             mass_trace=[{'step':i, 'mass_kg':1.} for i in range(1001)])
    return dict(provenance='native-device', producer_sha256={k:'a'*64 for k in REQUIRED_SOURCES},
                cases={k:copy.deepcopy(c) for k in ('bounce','first_layer','second_layer')},
                no_force_double_mirror=dict(steps=1000,F=0,top_specular=True,
                    bottom_specular=True,wall_stress_forced_zero=True,
                    px_trace=[{'step':i,'Px_kg_m_s':1.} for i in range(1001)]))


def selftest():
    f=fixture()
    assert len(validate(copy.deepcopy(f)))==4
    tests = {
      'short_A7':lambda p:p['cases']['bounce']['half_turnover_windows'][0].__setitem__('step_end',1000),
      'bad_dt':lambda p:p['cases']['bounce']['half_turnover_windows'][0].__setitem__('dt_s',1.),
      'missing_bounce':lambda p:p['cases']['bounce']['half_turnover_windows'][0]['ground_components_N'].pop('bounce'),
      'wrong_sign':lambda p:p['cases']['bounce']['half_turnover_windows'][0]['ground_components_N'].__setitem__('bounce',-1.),
      'top_mismatch':lambda p:p['cases']['bounce']['half_turnover_windows'][0].__setitem__('top_DDF_N',1.),
      'missing_mass_step':lambda p:p['cases']['bounce']['mass_trace'].pop(3),
      'missing_px_step':lambda p:p['no_force_double_mirror']['px_trace'][4].__setitem__('step',5),
      'bad_manifest':lambda p:p['producer_sha256'].__setitem__('DDF_before_after_top_links','fixture'),
    }
    for label, mutate in tests.items():
        p=copy.deepcopy(f); mutate(p)
        try: validate(p)
        except (ValueError,AssertionError) as e: print('EXPECTED_REJECT',label,str(e))
        else: raise AssertionError(f'missed negative fixture: {label}')
    print('FIXTURE_PASS: time axis and ledger negatives only; NO native GPU gates measured')

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--self-test',action='store_true'); ap.add_argument('input',nargs='?',type=Path)
    args=ap.parse_args()
    if args.self_test: selftest()
    elif args.input: print(json.dumps(validate(json.loads(args.input.read_text())),indent=2))
    else: ap.error('native evidence JSON or --self-test required')
