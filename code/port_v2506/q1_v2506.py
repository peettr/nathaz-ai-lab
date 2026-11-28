#!/usr/bin/env python3
"""Compare actual p solver log to independently recomputed exported-system residuals."""
import csv
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
# Legacy parser is serial and works without the optional threadpoolctl module.
from scipy.io._mmio import mmread
from scipy.sparse.linalg import norm

pressure = re.compile(r'^(\S+):\s+Solving for p,\s+Initial residual = (\S+),\s+Final residual = (\S+),\s+No Iterations (\d+)\s*$')
marker = re.compile(r'^LINSYS_BEGIN (\d+) (\d+) (p(?:Final)?)$')


def rel(x, ref):
    if ref == 0:
        return 0. if x == 0 else math.inf
    return abs(x-ref)/abs(ref)


def audit(root, name, moving):
    log=(root/'log.solve').read_text().splitlines()
    assert any(l.strip()=='End' for l in log), root
    steps=[l.split('=',1)[1].strip() for l in log if l.startswith('Time = ')]
    assert len(steps)==5, (root, steps)
    pending=None
    records={}
    for line in map(str.strip,log):
        if m:=marker.fullmatch(line):
            assert pending is None
            pending=tuple(m.groups())
        if m:=pressure.fullmatch(line):
            assert pending is not None and pending[:2] not in records
            records[pending[:2]]=(pending[2],*m.groups())
            pending=None
    assert pending is None
    # Stock selected cases each have two pEqn solves per step.
    expected={(str(i),str(j)) for i in range(1,6) for j in (1,2)}
    assert records.keys()==expected,(records.keys(),expected)
    assert {d.name for d in (root/'Solving').glob('PresCorr-*')} == {'PresCorr-'+'-'.join(k) for k in expected}
    rows=[]
    for key in sorted(records,key=lambda k:tuple(map(int,k))):
        i,j=map(int,key)
        system=f'PresCorr-{i}-{j}'
        d=root/'Solving'/system
        m=json.loads((d/'meta.json').read_text())
        select, solver, r0, rf, it=records[key]
        r0,rf,it=float(r0),float(rf),int(it)
        assert solver=='GAMG', solver
        assert m['step']==i and m['correction']==j and m['solver_entry']==select and m['is_final']==(select=='pFinal')
        assert float(m['time'])==float(steps[i-1]) and m['iterations']==it
        assert rel(m['initial_residual'],r0)<=1e-5 and rel(m['final_residual'],rf)<=1e-5
        a=mmread(d/'A.mtx.gz').tocsr()
        a.sum_duplicates()
        b,x0,xf=(np.load(d/(file+'.npy'),allow_pickle=False) for file in ('b','x_initial','x_openfoam'))
        assert a.shape==(b.size,b.size) and x0.shape==xf.shape==b.shape==(b.size,)
        assert all(np.isfinite(v).all() for v in (a.data,b,x0,xf))
        ax0=a@x0
        ref=[邮箱](x0,x0.mean())
        nf=float(np.abs(ax0-ref).sum()+np.abs(b-ref).sum()+1e-20)
        initial=float(np.abs(b-ax0).sum()/nf)
        final=float(np.abs(b-a@xf).sum()/nf)
        ei,ef=rel(initial,r0),rel(final,rf)
        rows.append(dict(tutorial=name,system=system,time=m['time'],step=i,correction=j,is_final=m['is_final'],solver_entry=select,mesh_moving=m['mesh_moving'],n=b.size,nnz=a.nnz,initial_log=r0,final_log=rf,initial_recomputed=initial,final_recomputed=final,initial_relative_error=ei,final_relative_error=ef,iterations=it,norm_factor=nf,symmetry_ratio=float(norm(a-a.T)/norm(a)),negative_A_diag_all_positive=bool(np.all(a.diagonal()<0)),q1_pass=ei<=.01 and ef<=.01))
    assert any(r['mesh_moving'] for r in rows)==moving
    return rows

if __name__=='__main__':
    dest=Path(sys.argv[1])
    rows=audit(dest/'pitzDaily','v2506/RAS/pitzDaily',False)+audit(dest/'wingMotion/wingMotion2D_pimpleFoam','v2506/RAS/wingMotion2D_pimpleFoam',True)
    with (dest/'q1_residuals_v2506.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    summary={}
    for case in sorted({r['tutorial'] for r in rows}):
        rr=[r for r in rows if r['tutorial']==case]
        summary[case]=dict(count=len(rr),passed=sum(r['q1_pass'] for r in rr),max_initial_error=max(r['initial_relative_error'] for r in rr),max_final_error=max(r['final_relative_error'] for r in rr),max_symmetry_ratio=max(r['symmetry_ratio'] for r in rr),all_negative_A_diag_positive=all(r['negative_A_diag_all_positive'] for r in rr),moving_systems=sum(r['mesh_moving'] for r in rr))
    print(json.dumps(summary,indent=2))
    sys.exit(0 if all(r['q1_pass'] for r in rows) else 2)
