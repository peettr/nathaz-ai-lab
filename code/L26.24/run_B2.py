#!/usr/bin/env python3
"""B2: validate native IC0 kernel, then run bounded 60-system benchmark on CRC."""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from baseline_B2_worker import lib, run

ROOTS = {
    't0': '/groups/kareem/[用户]/L26_24_LINSYS_20261114/Solving',
    'restart': '/groups/kareem/[用户]/L26_24_LINSYS_20261115_D1/segments/restart/Solving',
    'later': '/groups/kareem/[用户]/L26_24_LINSYS_20261115_D1b/segments/later/Solving',
}

def validate():
    # SPD tridiagonal with hand-verified L on a zero-fill pattern.
    a = csr_matrix(np.array([[4., -1., 0.],[-1., 4., -1.],[0., -1., 4.]]))
    l = csr_matrix(np.tril(a.toarray()))
    v = np.empty_like(l.data)
    assert lib.ic0_factor(3, l.indptr, l.indices, l.data, v) == 0
    l.data = v
    assert np.allclose((l @ l.T).toarray(), a.toarray(), atol=1e-12)
    u = l.T.tocsr()
    rhs = np.array([1., 2., 3.]); work = np.empty_like(rhs); out = np.empty_like(rhs)
    lib.ic0_apply(3, l.indptr, l.indices, l.data, u.indptr, u.indices,
                  u.data, rhs, work, out)
    assert np.allclose(a @ out, rhs, atol=1e-12)
    print('IC0_TOY_PASS', flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    args=p.parse_args()
    validate()
    out=Path(args.out); out.mkdir(exist_ok=True)
    items=[(seg,d) for seg,root in ROOTS.items()
           for d in sorted(Path(root).glob('PresCorr-*'),key=lambda x:tuple(map(int,re.findall(r'\d+',x.name))))]
    assert {seg:sum(s==seg for s,_ in items) for seg in ROOTS}==dict.fromkeys(ROOTS,20)
    assert all(os.getenv(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
    start=time.monotonic(); done=0
    for seg,d in items:
        for target in ('Ta','Tb'):
            dest=out/f'{seg}_{d.name}_{target}.json'
            assert not dest.exists(),dest
            result=run(d,target,5)
            result.update(segment=seg,split='test' if seg=='later' else 'train',
                          cpu_model=next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),'unavailable'))
            with dest.open('x') as f: json.dump(result,f)
            done+=1
            elapsed=time.monotonic()-start
            print('PAIR',seg,d.name,target,'elapsed',elapsed,'estimated_all',elapsed*120/done,flush=True)
            if done==1 and elapsed*120>3.5*3600:
                print('BUDGET_GATE_STOP first-pair estimate',flush=True); return 3
            if elapsed>3.5*3600:
                print('BUDGET_GATE_STOP elapsed',flush=True); return 3
    print('B2_COMPLETE',flush=True)
    return 0

if __name__=='__main__':sys.exit(main())
