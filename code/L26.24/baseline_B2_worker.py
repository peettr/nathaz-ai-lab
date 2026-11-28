#!/usr/bin/env python3
"""B2 exact IC(0)+CG on one immutable OpenFOAM export, CRC only."""
import ctypes as c
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.io import mmread
from scipy.sparse import tril
from scipy.sparse.linalg import LinearOperator, cg

from baseline_B1_worker import ReachedTarget, residual

I = np.ctypeslib.ndpointer(dtype=np.int32, flags='C_CONTIGUOUS')
D = np.ctypeslib.ndpointer(dtype=np.float64, flags='C_CONTIGUOUS')
lib = c.CDLL(str(Path(__file__).resolve().parent / 'libic0_B2.so'))
lib.ic0_factor.argtypes = [c.c_int, I, I, D, D]
lib.ic0_factor.restype = c.c_int
lib.ic0_apply.argtypes = [c.c_int, I, I, D, I, I, D, D, D, D]
lib.ic0_apply.restype = None


def load(folder):
    d = Path(folder)
    meta = json.loads((d / 'meta.json').read_text())
    A = -mmread(str(d / 'A.mtx.gz')).tocsr().astype(np.float64)
    A.sum_duplicates(); A.sort_indices()
    b = -np.load(d / 'b.npy')
    x0 = np.load(d / 'x_initial.npy')
    assert A.shape == (len(b), len(b)) and b.shape == x0.shape
    assert np.all(A.diagonal() > 0)
    ref = A @ np.full_like(x0, np.mean(x0))
    factor = float(np.abs(A @ x0 - ref).sum() + np.abs(b - ref).sum() + 1e-20)
    return A, b, x0, factor, meta


def run(folder, target, repeat):
    A, b, x0, factor, meta = load(folder)
    initial = residual(A, b, x0, factor)
    tol = max(1e-6, .05 * initial) if target == 'Ta' and not meta['is_final'] else (1e-6 if target == 'Ta' else 1e-8)
    lower = tril(A, format='csr')
    lower.sort_indices()
    original_data = lower.data.copy()
    assert lower.indptr.dtype == np.int32 and lower.indices.dtype == np.int32
    results = []
    for rep in range(repeat):
        start = time.perf_counter()
        values = np.empty_like(lower.data)
        problem_row = lib.ic0_factor(A.shape[0], lower.indptr, lower.indices,
                                     original_data, values)
        if problem_row:
            raise ArithmeticError(f'IC0 breakdown row {problem_row} in {folder}')
        lower.data = values
        upper = lower.T.tocsr()
        upper.sort_indices()
        assert upper.indptr.dtype == np.int32 and upper.indices.dtype == np.int32
        setup = time.perf_counter() - start
        work = np.empty_like(b)
        def apply(v):
            out = np.empty_like(v)
            lib.ic0_apply(A.shape[0], lower.indptr, lower.indices, lower.data,
                          upper.indptr, upper.indices, upper.data,
                          np.ascontiguousarray(v), work, out)
            return out
        M = LinearOperator(A.shape, matvec=apply, dtype=np.float64)
        counter = [0]
        def monitor(x):
            counter[0] += 1
            r = residual(A, b, x, factor)
            if r <= tol:
                raise ReachedTarget(x.copy(), r, counter[0])
        start = time.perf_counter()
        if initial <= tol:
            final, iterations, status = initial, 0, 'initial_meets_target'
        else:
            try:
                x, info = cg(A, b, x0=x0, M=M, rtol=1e-14, atol=0,
                             maxiter=20000, callback=monitor)
                final = residual(A, b, x, factor)
                iterations, status = counter[0], ('converged' if final <= tol else f'not_met_cg_info_{info}')
            except ReachedTarget as hit:
                final, iterations, status = hit.residual_value, hit.iterations, 'converged'
        solve = time.perf_counter() - start
        results.append(dict(repetition=rep, setup_seconds=setup, solve_seconds=solve,
                            total_seconds=setup+solve, iterations=iterations,
                            achieved_residual=final, status=status))
        del M, upper
    return dict(system=Path(folder).name, target=target, baseline='B2_IC0_CG',
                initial_residual=initial, target_residual=tol, n=A.shape[0],
                nnz=A.nnz, source=str(folder), results=results,
                thread_env={k:os.getenv(k) for k in
                            ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')})

if __name__ == '__main__':
    d, target, out = sys.argv[1:4]
    with Path(out).open('x') as f:
        json.dump(run(d, target, 5), f)
