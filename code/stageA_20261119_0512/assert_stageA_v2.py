#!/usr/bin/env python3
"""T17 v2 A1/A2/A3/A7 fail-closed validator; input must be native evidence.

This script never creates measurements. `--self-test` exercises synthetic gate edges
only and cannot qualify the GPU branch. The producer must archive raw time traces,
flags and DDF top exchange with SHA sidecars separately.
"""
import argparse
import json
import math
from pathlib import Path

NX, NY, H = 256, 128, 64
AREA = NX * NY


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name}: missing/nonfinite numeric value")
    return float(value)


def ratio_change(a, b, name):
    a, b = finite(a, name + '.initial'), finite(b, name + '.final')
    if a == 0:
        raise ValueError(name + ': zero initial denominator')
    return abs(b - a) / abs(a)


def check(payload):
    if payload.get('provenance') != 'native-device':
        raise ValueError('requires native-device evidence (not host flags or fixture)')
    result = {}
    cases = payload['cases']
    if set(cases) != {'bounce', 'first_layer', 'second_layer'}:
        raise ValueError('A1/A2/A7 require exactly three ground treatments')
    for name, case in cases.items():
        if case.get('steps') != 1000:
            raise ValueError(f'{name}: A1 window must be exactly 1000 steps')
        mass = ratio_change(case['mass'][0], case['mass'][1], name + '.mass')
        if mass > 1e-5:
            raise AssertionError(f'{name}: A1a mass change {mass} > 1e-5')
        f = finite(case['F'], name + '.F')
        if f <= 0:
            raise ValueError(name + ': positive SI unit-mass F required')
        rho = finite(case['rho'], name + '.rho')
        if rho <= 0:
            raise ValueError(name + ': positive rho required')
        top = abs(finite(case['top_ddf_flux'], name + '.top_ddf_flux'))
        top_ratio = top / (f * H)
        if top_ratio > 0.01:
            raise AssertionError(f'{name}: A2 top DDF flux ratio {top_ratio} > 0.01')
        flags = case['native_flag_eligibility']
        if not isinstance(flags, list) or len(flags) != AREA or any(x is not True for x in flags):
            raise AssertionError(f'{name}: A3 requires {AREA} true native columns')
        windows = case['half_turnover_windows']
        if not windows:
            raise ValueError(f'{name}: no A7 windows')
        residuals = []
        for i, w in enumerate(windows):
            dt = finite(w['dt_s'], f'{name}.windows[{i}].dt_s')
            if dt <= 0:
                raise ValueError('A7 dt_s must be positive')
            # P and ground/top forces use compatible SI force units; signed
            # ground and top flux are positive for loss of +x momentum.
            dpdt = (finite(w['Px_final'], 'Px_final') - finite(w['Px_initial'], 'Px_initial')) / dt
            drive = rho * f * H * AREA
            residual = abs(dpdt - (drive - finite(w['F_ground_x'], 'F_ground_x') -
                                    finite(w['F_top_x'], 'F_top_x'))) / drive
            if residual > 0.01:
                raise AssertionError(f'{name}: A7 window {i} residual {residual} > 0.01')
            residuals.append(residual)
        result[name] = {'A1a_mass_relative': mass, 'A2_top_absolute_ratio': top_ratio,
                        'A3_native_eligible': len(flags), 'A7_residuals': residuals}
    b = payload['no_force_double_mirror']
    if b.get('steps') != 1000 or b.get('F') != 0 or not b.get('top_specular') or not b.get('bottom_specular') or not b.get('wall_stress_forced_zero'):
        raise ValueError('A1b requires zero-force, double-specular, zero-stress, 1000-step native case')
    px = ratio_change(b['Px'][0], b['Px'][1], 'A1b.Px')
    if px > 1e-5:
        raise AssertionError(f'A1b momentum change {px} > 1e-5')
    result['A1b'] = {'momentum_relative': px}
    return result


def self_test():
    # Fixture only; intentionally small numerical values but full native flag shape.
    case = {'steps': 1000, 'mass': [1., 1.], 'rho': 1., 'F': 0.001,
            'top_ddf_flux': 0., 'native_flag_eligibility': [True] * AREA,
            'half_turnover_windows': [{'dt_s': 1., 'Px_initial': 1.,
                                        'Px_final': 1. + 0.001 * H * AREA,
                                        'F_ground_x': 0., 'F_top_x': 0.}]}
    fixture = {'provenance': 'native-device', 'cases': {k: dict(case) for k in
               ('bounce', 'first_layer', 'second_layer')},
               'no_force_double_mirror': {'steps': 1000, 'F': 0, 'top_specular': True,
                   'bottom_specular': True, 'wall_stress_forced_zero': True, 'Px': [1., 1.]}}
    assert len(check(fixture)) == 4
    import copy
    for label, mutate in [
        ('bad-mass', lambda p: p['cases']['bounce'].__setitem__('mass', [1., 1.001])),
        ('bad-top-flux-sign', lambda p: p['cases']['bounce'].__setitem__('top_ddf_flux', -0.001)),
        ('bad-flag', lambda p: p['cases']['bounce']['native_flag_eligibility'].__setitem__(0, False)),
        ('bad-closure', lambda p: p['cases']['bounce']['half_turnover_windows'][0].__setitem__('F_ground_x', 100.)),
        ('bad-momentum', lambda p: p['no_force_double_mirror'].__setitem__('Px', [1., 1.001])),
        ('host-only', lambda p: p.__setitem__('provenance', 'host-flags')),
    ]:
        trial = copy.deepcopy(fixture)
        mutate(trial)
        try:
            check(trial)
        except (AssertionError, ValueError) as exc:
            print(f'EXPECTED_REJECT {label}: {exc}')
        else:
            raise AssertionError(f'failed to reject {label}')
    print('FIXTURE_PASS: synthetic tests only; native gates remain unmeasured')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('evidence', nargs='?', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.evidence:
        print(json.dumps(check(json.loads(args.evidence.read_text())), indent=2))
    else:
        parser.error('provide native evidence JSON or --self-test')
