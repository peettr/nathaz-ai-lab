#!/usr/bin/env python3
"""Postprocess exported OF10 sparse systems (run on CRC, not 工作站)."""
import csv
import gzip
import hashlib
import json
import re
from pathlib import Path
import numpy as np
import scipy.io
import scipy.sparse as sp

root = Path(__import__('sys').argv[1])
solving = root/'Solving'
rows = []
sha = hashlib.sha256()
for f in [root/'case_dump/system/controlDict', root/'case_dump/system/fvSolution', root/'src/pimpleFoam.C',root/'src/pEqn.H']:
    sha.update(f.read_bytes())
config_hash=sha.hexdigest()
for d in sorted(solving.glob('PresCorr-*'), key=lambda p: tuple(map(int,re.findall(r'\d+',p.name)))):
    m=json.loads((d/'meta.json').read_text())
    A=sp.csr_matrix(scipy.io.mmread(d/'A.mtx.gz'), dtype=np.float64)
    A.sum_duplicates()
    sp.save_npz(d/'A.npz',A,compressed=True)
    b=np.load(d/'b.npy')
    x0=np.load(d/'x_initial.npy')
    x=np.load(d/'x_openfoam.npy')
    assert A.shape==(len(b),len(b)) and len(x)==len(b)==len(x0)
    def residual(z):
        avg=float(np.mean(z))
        az=A@z
        aavg=[邮箱](len(z),avg)
        return float(np.abs(b-az).sum()/(np.abs(az-aavg).sum()+np.abs(b-aavg).sum()))
    ri=residual(x0)
    rf=residual(x)
    ei=abs(ri-m['initial_residual'])/max(abs(m['initial_residual']),1e-300)
    ef=abs(rf-m['final_residual'])/max(abs(m['final_residual']),1e-300)
    diff=A-A.T
    asym=float(sp.linalg.norm(diff)/sp.linalg.norm(A))
    diag_neg=bool(np.all(-A.diagonal()>0))
    m['config_sha256']=config_hash
    m['source']='R25.2 S2-derived nutcheck/case read-only copy; OpenFOAM Foundation 10'
    m.update(n=int(A.shape[0]), nnz=int(A.nnz),npz_bytes=(d/'A.npz').stat().st_size,mtx_gz_bytes=(d/'A.mtx.gz').stat().st_size,initial_recomputed=ri,final_recomputed=rf,initial_rel_error=ei,final_rel_error=ef,asymmetry=asym,negative_diagonal_positive=diag_neg,q1_pass=ei<=.01 and ef<=.01)
    (d/'meta.json').write_text(json.dumps(m,indent=2)+'\n')
    rows.append(m)
    print(d.name,m['n'],m['nnz'],ei,ef,flush=True)
with (root/'q1_q2.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(root/'q1_summary.json').write_text(json.dumps({'count':len(rows),'all_pass':len(rows)==20 and all(r['q1_pass'] for r in rows),'config_sha256':config_hash},indent=2)+'\n')
