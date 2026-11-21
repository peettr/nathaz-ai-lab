#!/usr/bin/env python3
"""Read-only streaming audit of pre-existing pressure exports; run on CRC."""
import csv, io, json, re, sys
from pathlib import Path
import numpy as np
import scipy.io
import scipy.sparse as sp

old, out = map(Path, sys.argv[1:3])
rows=[]
for d in sorted((old/'Solving').glob('PresCorr-*'),key=lambda p: tuple(map(int,re.findall(r'\d+',p.name)))):
    m=json.loads((d/'meta.json').read_text())
    A=scipy.io.mmread(str(d/'A.mtx.gz')).tocsr().astype(np.float64)
    A.sum_duplicates()
    b=np.load(d/'b.npy'); x0=np.load(d/'x_initial.npy'); x=np.load(d/'x_openfoam.npy')
    assert A.shape==(len(b),len(b)) and x.shape==x0.shape==b.shape
    def residual(z):
        az=A@z; aavg=[邮箱](z, np.mean(z))
        return float(np.abs(b-az).sum()/(np.abs(az-aavg).sum()+np.abs(b-aavg).sum()))
    ri,rf=residual(x0),residual(x)
    ei=abs(ri-m['initial_residual'])/max(abs(m['initial_residual']),1e-300)
    ef=abs(rf-m['final_residual'])/max(abs(m['final_residual']),1e-300)
    diff=A-A.T
    norm_sq=float(A.multiply(A).sum())
    asym=float(np.sqrt(float(diff.multiply(diff).sum())/norm_sq))
    rec={'system':d.name,'n':int(A.shape[0]),'csr_nnz':int(A.nnz),'mtx_gz_bytes':(d/'A.mtx.gz').stat().st_size,
         'openfoam_initial':m['initial_residual'],'recomputed_initial':ri,'initial_relative_error':ei,
         'openfoam_final':m['final_residual'],'recomputed_final':rf,'final_relative_error':ef,
         'q1_pass':ei<=.01 and ef<=.01,'asymmetry_ratio':asym,'minus_A_diagonal_all_positive':bool(np.all(-A.diagonal()>0)),
         'npz_bytes':None}
    if not rows:
        buf=io.BytesIO(); sp.save_npz(buf,A,compressed=True); rec['npz_bytes']=buf.tell()
    rows.append(rec); print(d.name,ei,ef,flush=True)
    del A,b,x0,x,diff
assert len(rows)==20, len(rows)
with (out/'q1_residuals.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader();w.writerows(rows)
(out/'q1_summary.json').write_text(json.dumps({'count':len(rows),'all_pass':all(r['q1_pass'] for r in rows),
 'failed_systems':[r['system'] for r in rows if not r['q1_pass']],
 'representative_npz_bytes':rows[0]['npz_bytes'],'representative_system':rows[0]['system'],
 'max_initial_relative_error':max(r['initial_relative_error'] for r in rows),
 'max_final_relative_error':max(r['final_relative_error'] for r in rows),
 'source':'R25.2 S2-derived OpenFOAM10 t=0 export, read-only D0 root'},indent=2)+'\n')
