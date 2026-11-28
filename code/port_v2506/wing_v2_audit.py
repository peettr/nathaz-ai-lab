"""Emit moving-wing Q1 and mesh-point displacement evidence."""
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np
from q1_v2506 import audit


def points(path):
    text = path.read_text().split('}', 1)[1]
    match = re.search(r'^\s*(\d+)\s*\(\s*\(', text, re.M)
    if not match:
        raise ValueError(f'No ASCII point list: {path}')
    n = int(match[1])
    values = np.array([v.split() for v in re.findall(r'\(([^()]*)\)', text[match.end()-1:])][:n], dtype=float)
    assert values.shape == (n, 3) and np.isfinite(values).all(), path
    return values


def main(case, out):
    rows = audit(case, 'v2506/RAS/wingMotion2D_pimpleFoam', True)
    with (out/'q1_wing_v2.csv').open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    ref = points(case/'constant/polyMesh/points')
    movement = []
    for time in dict.fromkeys(str(r['time']) for r in rows):
        path, = (p for p in case.glob('*/polyMesh/points') if p.parent.parent.name != 'constant' and float(p.parent.parent.name) == float(time))
        delta = np.linalg.norm(points(path) - ref, axis=1)
        movement.append(dict(time=time, file=str(path.relative_to(case)), points=len(delta), max_displacement_m=float(delta.max()), nonzero_points=int(np.count_nonzero(delta))))
    summary = dict(count=len(rows), passed=sum(r['q1_pass'] for r in rows), max_initial_error=max(r['initial_relative_error'] for r in rows), max_final_error=max(r['final_relative_error'] for r in rows), max_symmetry_ratio=max(r['symmetry_ratio'] for r in rows), all_negative_A_diag_positive=all(r['negative_A_diag_all_positive'] for r in rows), movement=movement)
    with (out/'q1_wing_v2_summary.json').open('x') as f:
        json.dump(summary, f, indent=2, allow_nan=False)
    print(json.dumps(summary, indent=2))
    return 0 if summary['passed'] == summary['count'] and any(r['max_displacement_m'] > 0 for r in movement) else 2


if __name__ == '__main__':
    sys.exit(main(*map(Path, sys.argv[1:])))
