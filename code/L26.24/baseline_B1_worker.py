#!/usr/bin/env python3
"""Single-system PyAMG+CG benchmark on a CRC compute node; writes one small JSON.

Run only after auditing/installing PyAMG in isolated run-root venv. Input is immutable.
"""
import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
from scipy.io import mmread
from scipy.sparse.linalg import LinearOperator, cg


def residual(A, b, x, factor):
    return float(np.abs(b - A @ x).sum() / factor)


class ReachedTarget(Exception):
    def __init__(self, x, residual_value, iterations):
        self.x, self.residual_value, self.iterations = x, residual_value, iterations


def run(folder, target, repeat):
    import pyamg
    folder = Path(folder)
    meta = json.loads((folder / 'meta.json').read_text())
    A = -mmread(str(folder / 'A.mtx.gz')).tocsr().astype(np.float64)
    A.sum_duplicates()
    A.sort_indices()
    b = -np.load(folder / 'b.npy')
    x0 = np.load(folder / 'x_initial.npy')
    assert A.shape == (len(b), len(b)) and x0.shape == b.shape
    assert np.all(A.diagonal() > 0)
    ref = A @ np.full_like(x0, np.mean(x0))
    factor = float(np.abs(A @ x0 - ref).sum() + np.abs(b - ref).sum() + 1e-20)
    initial = residual(A, b, x0, factor)
    tol = max(1e-6, .05 * initial) if target == 'Ta' and not meta['is_final'] else (1e-6 if target == 'Ta' else 1e-8)
    output = []
    for rep in range(repeat):
        t0 = time.perf_counter()
        ml = pyamg.smoothed_aggregation_solver(A)
        setup = time.perf_counter() - t0
        M = ml.aspreconditioner(cycle='V')
        counter = [0]
        def monitor(x):
            counter[0] += 1
            r = residual(A, b, x, factor)
            if r <= tol:
                raise ReachedTarget(x.copy(), r, counter[0])
        t0 = time.perf_counter()
        if initial <= tol:
            x, final, iterations, status = x0.copy(), initial, 0, 'initial_meets_target'
        else:
            try:
                x, info = cg(A, b, x0=x0, M=M, rtol=1e-14, atol=0,
                             maxiter=20000, callback=monitor)
                final = residual(A, b, x, factor)
                iterations, status = counter[0], ('converged' if final <= tol else f'not_met_cg_info_{info}')
            except ReachedTarget as done:
                x, final, iterations, status = done.x, done.residual_value, done.iterations, 'converged'
        solve = time.perf_counter() - t0
        output.append(dict(repetition=rep, setup_seconds=setup, solve_seconds=solve,
                           total_seconds=setup+solve, iterations=iterations,
                           achieved_residual=final, status=status))
        del ml, M
    return dict(system=folder.name, target=target, baseline='B1_PyAMG_SA_CG',
                initial_residual=initial, target_residual=tol,
                n=A.shape[0], nnz=A.nnz, thread_env={k:os.environ.get(k) for k in
                ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
                source=str(folder), results=output)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('system')
    p.add_argument('target', choices=('Ta','Tb'))
    p.add_argument('out')
    p.add_argument('--repeat', type=int, default=5)
    args = p.parse_args()
    assert args.repeat > 0
    dest = Path(args.out)
    assert not dest.exists(), dest
    result = run(args.system, args.target, args.repeat)
    with dest.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
