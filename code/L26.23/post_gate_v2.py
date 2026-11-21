#!/usr/bin/env python3
"""Fail-closed OpenFOAM 10 final nut gate; preserve earlier post_gate.py."""
import argparse
import json
import math
import re
import subprocess
from pathlib import Path

NUM = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'


def scalars(path, key):
    p = subprocess.run(['foamDictionary', '-entry', key, '-value', str(path)],
                       capture_output=True, text=True)
    if p.returncode:
        raise ValueError(f'{path} {key}: foamDictionary failed: {p.stderr[-500:]}')
    s = p.stdout.strip()
    if re.fullmatch(r'uniform\s+' + NUM + r'\s*;?', s):
        return [float(re.search(NUM, s).group())]
    m = re.fullmatch(r'nonuniform\s+List<scalar>\s+(\d+)\s*\((.*)\)\s*;?', s, re.S)
    if not m:
        raise ValueError(f'{path} {key}: unsupported field representation: {s[:100]}')
    n = int(m.group(1))
    vals = m.group(2).split()
    if len(vals) != n or n < 1 or not all(re.fullmatch(NUM, v) for v in vals):
        raise ValueError(f'{path} {key}: field count/token mismatch')
    return list(map(float, vals))


def gate(root, end, ranks=48, serial=False):
    log = (root / 'log.pimpleFoam').read_text(errors='replace')
    times = [float(x) for x in re.findall(r'(?m)^Time =\s*(' + NUM + r')\s*s?\s*$', log)]
    result = {'End': bool(re.search(r'(?m)^End\s*$', log)),
              'last_time': times[-1] if times else None,
              'final_time_ok': bool(times and math.isfinite(times[-1]) and abs(times[-1] - end) < 1e-7),
              'ranks': 0, 'internal_count': 0, 'building_count': 0,
              'building_uniform_zero_ranks': 0, 'internal_min': None,
              'internal_max': None, 'building_max_abs': None}
    if not (result['End'] and result['final_time_ok']):
        raise ValueError('solver end/time gate failed')
    if serial and ranks != 1:
        raise ValueError('serial validation requires exactly one rank')
    for rank in range(ranks):
        d = root / 'case' if serial else root / 'case' / f'processor{rank}'
        if not d.is_dir():
            raise ValueError(f'{d}: missing directory')
        matches = [x / 'nut' for x in d.iterdir()
                   if x.is_dir() and re.fullmatch(NUM, x.name)
                   and abs(float(x.name) - end) < 1e-7 and (x / 'nut').is_file()]
        if len(matches) != 1:
            raise ValueError(f'processor{rank}: missing/ambiguous final nut')
        f = matches[0]
        internal = scalars(f, 'internalField')
        building = scalars(f, 'boundaryField/building/value')
        if not internal or not building:
            raise ValueError(f'{f}: empty nut')
        if not all(math.isfinite(x) and x >= 0 for x in internal + building):
            raise ValueError(f'{f}: nonfinite/negative nut')
        if any(x != 0 for x in building):
            raise ValueError(f'{f}: nonzero building nut')
        result['ranks'] += 1
        result['internal_count'] += len(internal)
        result['building_count'] += len(building)
        if len(building) == 1:
            result['building_uniform_zero_ranks'] += 1
        lo, hi = min(internal), max(internal)
        result['internal_min'] = lo if result['internal_min'] is None else min(result['internal_min'], lo)
        result['internal_max'] = hi if result['internal_max'] is None else max(result['internal_max'], hi)
    if result['ranks'] != ranks or result['building_count'] < ranks:
        raise ValueError('incomplete building patch/ranks')
    result['building_max_abs'] = 0.0
    result['pass'] = True
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--end', type=float, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--serial-validation', action='store_true', help='validate single serial smoke; production remains 48 ranks')
    a = p.parse_args()
    if a.out.exists():
        raise FileExistsError(a.out)
    try:
        result = gate(a.root, a.end, ranks=1 if a.serial_validation else 48,
                      serial=a.serial_validation)
    except Exception as e:
        result = {'pass': False, 'error': str(e)}
    a.out.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(result)
    if not result['pass']:
        raise SystemExit(1)
