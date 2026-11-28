#!/usr/bin/env python3
"""B1 single-core CRC benchmark; immutable source systems; bounded pilot gate."""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from baseline_B1_worker import run

ROOTS = {
    't0': '/groups/kareem/[用户]/L26_24_LINSYS_20261114/Solving',
    'restart': '/groups/kareem/[用户]/L26_24_LINSYS_20261115_D1/segments/restart/Solving',
    'later': '/groups/kareem/[用户]/L26_24_LINSYS_20261115_D1b/segments/later/Solving',
}

def key(p):
    return tuple(map(int, re.findall(r'\d+', p.name)))

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    p.add_argument('--pilot-only', action='store_true')
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    items = [(segment, d) for segment, root in ROOTS.items()
             for d in sorted(Path(root).glob('PresCorr-*'), key=key)]
    counts = {segment: sum(s == segment for s, _ in items) for segment in ROOTS}
    assert counts == {'t0': 20, 'restart': 20, 'later': 20}, counts
    assert all(os.environ.get(k) == '1' for k in
               ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'))
    started = time.monotonic()
    done = 0
    for segment, folder in items:
        for target in ('Ta', 'Tb'):
            dest = out / f'{segment}_{folder.name}_{target}.json'
            assert not dest.exists(), dest
            t0 = time.monotonic()
            result = run(folder, target, 5)
            result['segment'] = segment
            result['split'] = 'test' if segment == 'later' else 'train'
            result['cpu_model'] = next((line.split(':', 1)[1].strip()
                                        for line in Path('/proc/cpuinfo').read_text().splitlines()
                                        if line.startswith('model name')), 'unavailable')
            result['elapsed_pair_seconds'] = time.monotonic() - t0
            with dest.open('x') as f:
                json.dump(result, f, indent=2)
                f.write('\n')
            done += 1
            elapsed = time.monotonic() - started
            print('PAIR', segment, folder.name, target, 'elapsed', elapsed,
                  'estimated_all', elapsed * 120 / done, flush=True)
            if done == 1 and elapsed * 120 > 3.5 * 3600:
                print('BUDGET_GATE_STOP: first pair extrapolation exceeds 3.5h', flush=True)
                return 3
            if args.pilot_only:
                print('PILOT_STOP', flush=True)
                return 0
            if elapsed > 3.5 * 3600:
                print('BUDGET_GATE_STOP: 3.5h elapsed', flush=True)
                return 3
    print('B1_COMPLETE', flush=True)
    return 0

if __name__ == '__main__':
    sys.exit(main())
