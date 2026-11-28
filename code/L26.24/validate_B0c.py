#!/usr/bin/env python3
import csv, json, sys
from collections import defaultdict
from pathlib import Path
path, mode, cores = sys.argv[1:]
rows = list(csv.DictReader(Path(path).open()))
by = defaultdict(list)
for r in rows:
    by[(r['time'], r['corr'], r['tier'])].append(r)
expected = 4 if mode == 'smoke' else 40
assert len(by) == expected, (len(by), expected)
assert len(rows) == expected * 5, len(rows)
checks = []
for k, vals in by.items():
    assert {int(v['rep']) for v in vals} == set(range(1, 6)), k
    assert {v['cores'] for v in vals} == {cores}, k
    initial = [float(v['initial_residual']) for v in vals]
    spread = max(initial)-min(initial)
    assert spread <= 1e-10 * max(1, max(abs(x) for x in initial)), (k, initial)
    checks.append({'key': list(k), 'initial': initial, 'spread': spread})
print(json.dumps({'mode': mode, 'cores': int(cores), 'rows': len(rows), 'groups': len(by), 'checks': checks}, indent=2))
