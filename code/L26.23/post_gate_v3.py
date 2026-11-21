#!/usr/bin/env python3
"""Fail-closed OF10 decomposed final-nut gate; empty building patches are valid."""
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
        return [float(re.search(NUM, s).group())], 'uniform'
    m = re.fullmatch(r'nonuniform\s+List<scalar>\s+(\d+)\s*\((.*)\)\s*;?', s, re.S)
    if not m:
        raise ValueError(f'{path} {key}: unsupported field representation: {s[:100]}')
    n = int(m.group(1))
    vals = m.group(2).split()
    if len(vals) != n or not all(re.fullmatch(NUM, v) for v in vals):
        raise ValueError(f'{path} {key}: field count/token mismatch')
    return list(map(float, vals)), 'nonuniform'


def gate(root, end, ranks=48):
    log = (root / 'log.pimpleFoam').read_text(errors='replace')
    times = [float(x) for x in re.findall(r'(?m)^Time =\s*(' + NUM + r')\s*s?\s*$', log)]
    result = {'End': bool(re.search(r'(?m)^End\s*$', log)),
              'last_time': times[-1] if times else None,
              'final_time_ok': bool(times and math.isfinite(times[-1]) and abs(times[-1] - end) < 1e-7),
              'ranks': 0, 'internal_count': 0, 'building_count': 0,
              'building_nonempty_ranks': 0, 'building_empty_ranks': 0,
              'internal_min': None, 'internal_max': None, 'building_max_abs': 0.0}
    if not (result['End'] and result['final_time_ok']):
        raise ValueError('solver end/time gate failed')
    for rank in range(ranks):
        d = root / 'case' / f'processor{rank}'
        if not d.is_dir():
            raise ValueError(f'{d}: missing directory')
        matches = [x / 'nut' for x in d.iterdir()
                   if x.is_dir() and re.fullmatch(NUM, x.name)
                   and abs(float(x.name) - end) < 1e-7 and (x / 'nut').is_file()]
        if len(matches) != 1:
            raise ValueError(f'processor{rank}: missing/ambiguous final nut')
        f = matches[0]
        internal, internal_repr = scalars(f, 'internalField')
        building, building_repr = scalars(f, 'boundaryField/building/value')
        if not internal or internal_repr != 'nonuniform':
            raise ValueError(f'{f}: empty/ambiguous internal nut')
        if not building and building_repr != 'nonuniform':
            raise ValueError(f'{f}: empty uniform building patch is invalid')
        if not all(math.isfinite(x) and x >= 0 for x in internal + building):
            raise ValueError(f'{f}: nonfinite/negative nut')
        if any(x != 0 for x in building):
            raise ValueError(f'{f}: nonzero building nut (rank {rank})')
        result['ranks'] += 1
        result['internal_count'] += len(internal)
        result['building_count'] += len(building)
        result['building_nonempty_ranks'] += bool(building)
        result['building_empty_ranks'] += not bool(building)
        lo, hi = min(internal), max(internal)
        result['internal_min'] = lo if result['internal_min'] is None else min(result['internal_min'], lo)
        result['internal_max'] = hi if result['internal_max'] is None else max(result['internal_max'], hi)
    if result['ranks'] != ranks or result['internal_count'] != 1144164 or result['building_count'] < 1:
        raise ValueError('incomplete ranks/cells/building patch: ' + json.dumps(result))
    result['pass'] = True
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--end', type=float, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise FileExistsError(a.out)
    try:
        result = gate(a.root, a.end)
    except Exception as e:
        result = {'pass': False, 'error': str(e)}
    a.out.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(result)
    if not result['pass']:
        raise SystemExit(1)
