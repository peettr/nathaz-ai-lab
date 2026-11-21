#!/usr/bin/env python3
"""Read-only D0c audit; run on CRC compute node. No large output."""
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np
import scipy.io

old, out = map(Path, sys.argv[1:3])
assert old.resolve() != out.resolve()
assert out.is_dir() and (old / 'Solving').is_dir()
rows = []
for d in sorted((old / 'Solving').glob('PresCorr-*'), key=lambda p: tuple(map(int, re.findall(r'\d+', p.name)))):
    m = json.loads((d / 'meta.json').read_text())
    A = scipy.io.mmread(str(d / 'A.mtx.gz')).tocsr().astype(np.float64)
    A.sum_duplicates()
    b = np.load(d / 'b.npy')
    initial = np.load(d / 'x_initial.npy')
    final = np.load(d / 'x_openfoam.npy')
    assert A.shape == (len(b), len(b)) and initial.shape == final.shape == b.shape
    ax_initial = A @ initial
    ref = A @ np.full_like(initial, np.mean(initial))
    norm_initial = float(np.abs(ax_initial - ref).sum() + np.abs(b - ref).sum() + 1e-20)
    ri = float(np.abs(b - ax_initial).sum() / norm_initial)
    ax_final = A @ final
    rf_source = float(np.abs(b - ax_final).sum() / norm_initial)
    ref_old = A @ np.full_like(final, np.mean(final))
    norm_old = float(np.abs(ax_final - ref_old).sum() + np.abs(b - ref_old).sum())
    rf_old = float(np.abs(b - ax_final).sum() / norm_old)
    ei = abs(ri - m['initial_residual']) / max(abs(m['initial_residual']), 1e-300)
    ef = abs(rf_source - m['final_residual']) / max(abs(m['final_residual']), 1e-300)
    ef_old = abs(rf_old - m['final_residual']) / max(abs(m['final_residual']), 1e-300)
    rows.append(dict(system=d.name, openfoam_initial=m['initial_residual'], recomputed_initial=ri,
                     initial_relative_error=ei, openfoam_final=m['final_residual'],
                     d0b_recomputed_final=rf_old, d0b_final_relative_error=ef_old,
                     source_recomputed_final=rf_source, source_final_relative_error=ef,
                     source_norm_factor=norm_initial, source_q1_pass=ei <= .01 and ef <= .01,
                     iterations=m.get('iterations')))
    print(d.name, 'source_final_relerr', ef, flush=True)
    del A, b, initial, final, ax_initial, ax_final
assert len(rows) == 20, len(rows)
with (out / 'q1_residuals_v2.csv').open('x', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
summary = dict(count=len(rows), source_pass_count=sum(r['source_q1_pass'] for r in rows),
               source_all_pass=all(r['source_q1_pass'] for r in rows),
               source_failed_systems=[r['system'] for r in rows if not r['source_q1_pass']],
               max_initial_relative_error=max(r['initial_relative_error'] for r in rows),
               max_source_final_relative_error=max(r['source_final_relative_error'] for r in rows),
               max_d0b_final_relative_error=max(r['d0b_final_relative_error'] for r in rows),
               source='R25.2 S2-derived OF10 t=0 pressure exports; D0 original read-only',
               definition='normFactor from initial psi and Apsi, reused for final; lduMatrixSolver.C:174-193 GAMGSolverSolve.C:43-68,121-130')
(out / 'q1_summary_v2.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
