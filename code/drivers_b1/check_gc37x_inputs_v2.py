#!/usr/bin/env python3
"""Frozen §6 input gate; inspect actual GC37 tensor or WRF real output, read-only.

Usage: check_gc37x_inputs_v2.py graphcast INPUT.nc [--json REPORT.json]
       check_gc37x_inputs_v2.py wrfinput wrfinput_d01 [--json REPORT.json]
No missing source is silently tolerated. Exit 0 only when all tests pass.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

GC37 = ('geopotential', 'temperature', 'u_component_of_wind',
        'v_component_of_wind', 'specific_humidity', 'vertical_velocity')
WRF = ('QVAPOR', 'T', 'P', 'PB', 'PH', 'PHB', 'U', 'V', 'PSFC',
       'TSK', 'SMOIS', 'TSLB')


def data(var, sel):
    a = var[sel]
    return np.asarray(np.ma.filled(a, np.nan), dtype=np.float64)


def check(path, kind):
    errors = []
    details = {}
    with Dataset(path, 'r') as ds:
        required = GC37 if kind == 'graphcast' else WRF
        for name in required:
            if name not in ds.variables:
                errors.append(f'{name}:missing')
        if errors:
            return {'path': str(path), 'kind': kind, 'passed': False, 'errors': errors}
        if kind == 'graphcast':
            levels = data(ds.variables['level'], slice(None)) if 'level' in ds.variables else np.array([])
            if levels.size != 37 or len(np.unique(levels)) != 37:
                errors.append(f'level:expected_37_unique_got_{levels.size}')
            order = np.argsort(levels)[::-1]  # pressure decreases upward
            for name in GC37:
                v = ds.variables[name]
                if 'level' not in v.dimensions or v.shape[v.dimensions.index('level')] != 37:
                    errors.append(f'{name}:37_levels_missing')
                    continue
                # One pressure slab at a time; retain the full globe for spatial checks.
                lev_axis = v.dimensions.index('level')
                slabs = {}
                for k in range(37):
                    sl = [slice(None)] * v.ndim
                    sl[lev_axis] = k
                    a = data(v, tuple(sl))
                    nbad = int(np.count_nonzero(~np.isfinite(a)))
                    if nbad:
                        errors.append(f'{name}:level={k}:nonfinite={nbad}')
                    finite = a[np.isfinite(a)]
                    if finite.size:
                        if name == 'specific_humidity' and (finite.min() < 0 or finite.max() > .04):
                            errors.append(f'{name}:level={k}:outside_[0,.04]')
                        if name == 'temperature' and (finite.min() < 150 or finite.max() > 350):
                            errors.append(f'{name}:level={k}:outside_[150,350]')
                        if name in ('u_component_of_wind', 'v_component_of_wind'):
                            limit = 150 if levels[k] >= 70 else 250
                            if np.max(np.abs(finite)) > limit:
                                errors.append(f'{name}:level={k}:wind_over_{limit}')
                    if name == 'geopotential':
                        slabs[k] = a
                if name == 'geopotential' and len(order) == 37:
                    for lower, upper in zip(order[:-1], order[1:]):
                        if np.any(slabs[upper] < slabs[lower]):
                            errors.append(f'geopotential:not_monotone:{levels[lower]}_to_{levels[upper]}')
            # All non-level tensors sent to inference, including forcing and static variables.
            for name, v in ds.variables.items():
                if name in required or name in ds.dimensions or name == 'datetime':
                    continue
                if v.dtype.kind not in 'fiu':
                    continue
                if np.any(~np.isfinite(data(v, slice(None)))):
                    errors.append(f'{name}:nonfinite')
            details['levels_hpa'] = levels.tolist()
        else:
            for name in WRF:
                v = ds.variables[name]
                dims = v.dimensions
                vertical = 'bottom_top' in dims
                lev_axis = dims.index('bottom_top') if vertical else None
                if name == 'QVAPOR' and not vertical:
                    errors.append('QVAPOR:no_bottom_top')
                nlev = v.shape[lev_axis] if vertical else 1
                for k in range(nlev):
                    sl = [slice(None)] * v.ndim
                    if vertical:
                        sl[lev_axis] = k
                    a = data(v, tuple(sl))
                    nbad = int(np.count_nonzero(~np.isfinite(a)))
                    if nbad:
                        errors.append(f'{name}:level={k}:nonfinite={nbad}')
                    finite = a[np.isfinite(a)]
                    if not finite.size:
                        continue
                    lo, hi = float(finite.min()), float(finite.max())
                    if name == 'QVAPOR':
                        if lo < 0 or hi > .04:
                            errors.append(f'QVAPOR:level={k}:outside_[0,.04]')
                        if hi - lo < 1e-9:
                            errors.append(f'QVAPOR:level={k}:constant_fake')
                    elif name == 'T' and (lo + 300 < 200 or hi + 300 > 700):
                        errors.append(f'T:level={k}:theta_outside_[200,700]')
                    elif name == 'PSFC' and (lo < 50000 or hi > 110000):
                        errors.append('PSFC:outside_[50,110]_kPa')
                    elif name in ('U', 'V') and max(abs(lo), abs(hi)) > 150:
                        errors.append(f'{name}:level={k}:wind_over_150')
            details['qvapor_levels'] = ds.variables['QVAPOR'].shape[ds.variables['QVAPOR'].dimensions.index('bottom_top')] if 'bottom_top' in ds.variables['QVAPOR'].dimensions else None
    return {'path': str(path), 'kind': kind, 'passed': not errors, 'errors': errors, 'details': details}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('kind', choices=['graphcast', 'wrfinput'])
    p.add_argument('path', type=Path)
    p.add_argument('--json', type=Path)
    a = p.parse_args()
    result = check(a.path, a.kind)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if a.json:
        if a.json.exists():
            raise FileExistsError(a.json)
        a.json.write_text(text + '\n')
    print(text)
    return 0 if result['passed'] else 2


if __name__ == '__main__':
    sys.exit(main())
