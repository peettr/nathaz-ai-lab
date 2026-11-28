#!/usr/bin/env python3
"""Stream 40 immutable pressure matrices, using OF10 initial normFactor."""
import csv, json, re, sys
from pathlib import Path
import numpy as np
import scipy.io
new=Path(sys.argv[1]); old=Path(sys.argv[2]); rows=[]
for segment,base in (('restart',old/'segments/restart/Solving'),('later',new/'segments/later/Solving')):
    dirs=sorted(base.glob('PresCorr-*'),key=lambda p: tuple(map(int,re.findall(r'\d+',p.name))))
    assert len(dirs)==20,(segment,len(dirs))
    for d in dirs:
        m=json.loads((d/'meta.json').read_text())
        A=scipy.io.mmread(str(d/'A.mtx.gz')).tocsr().astype(np.float64); A.sum_duplicates()
        b=np.load(d/'b.npy'); x0=np.load(d/'x_initial.npy'); x=np.load(d/'x_openfoam.npy')
        assert A.shape==(len(b),len(b)) and x0.shape==x.shape==b.shape
        a0=A@x0; ref=[邮箱](x0,np.mean(x0))
        norm=float(np.abs(a0-ref).sum()+np.abs(b-ref).sum()+1e-20)
        initial=float(np.abs(b-a0).sum()/norm)
        final=float(np.abs(b-A@x).sum()/norm)
        e0=abs(initial-m['initial_residual'])/max(abs(m['initial_residual']),1e-300)
        ef=abs(final-m['final_residual'])/max(abs(m['final_residual']),1e-300)
        diff=A-A.T
        symmetry=float(np.sqrt(diff.multiply(diff).sum()/A.multiply(A).sum()))
        negdiag=bool(np.all(-A.diagonal()>0))
        rows.append(dict(system=segment+'/'+d.name,segment=segment,time=m['time'],step=m['step'],correction=m['correction'],
                         openfoam_initial=m['initial_residual'],recomputed_initial=initial,initial_relative_error=e0,
                         openfoam_final=m['final_residual'],recomputed_final=final,final_relative_error=ef,
                         q1_pass=e0<=.01 and ef<=.01,symmetry_ratio=symmetry,minus_A_diag_all_positive=negdiag,
                         order=A.shape[0],csr_nnz=A.nnz,mtx_gz_bytes=(d/'A.mtx.gz').stat().st_size,
                         system_bytes=sum(p.stat().st_size for p in d.iterdir() if p.is_file())))
        print(rows[-1]['system'],'final_relative_error',ef,flush=True)
        del A,b,x0,x,a0,ref,diff
assert len(rows)==40
with (new/'q1_residuals_D1.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
summary=dict(source='R25.2 S2 checkpoint 44; old D1 restart read-only; D1b later',
             definition='OF10 normFactor from initial psi and Apsi reused for final',
             count=len(rows),pass_count=sum(r['q1_pass'] for r in rows),all_pass=all(r['q1_pass'] for r in rows),
             failed_systems=[r['system'] for r in rows if not r['q1_pass']],
             max_initial_relative_error=max(r['initial_relative_error'] for r in rows),
             max_final_relative_error=max(r['final_relative_error'] for r in rows),
             max_symmetry_ratio=max(r['symmetry_ratio'] for r in rows),
             minus_A_diag_all_positive=all(r['minus_A_diag_all_positive'] for r in rows),
             per_system_bytes={r['system']:r['system_bytes'] for r in rows})
(new/'q1_summary_D1.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='per_system_bytes'},indent=2),flush=True)
if not summary['all_pass']: sys.exit(82)
