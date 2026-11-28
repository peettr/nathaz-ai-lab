#!/usr/bin/env python3
"""Derive C2a diagnostic-only package from immutable third-run scripts."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parent
source=root.parent/'third'
assert not any(root.glob('c2a_*')) and not (root/'harvest.py').exists(), 'Refuse overwrite'
for name in ('c2a_solve.qsub','c2a_driver.py','c2a_worker.sh','rss_sampler.py','harvest.py'):
    shutil.copyfile(source/name,root/name)
for name in ('c2a_driver.py','c2a_solve.qsub','c2a_worker.sh'):
    p=root/name
    s=p.read_text()
    if name=='c2a_driver.py':
        old="extra=sorted((i for i in range(n) if i not in ids),key=lambda i:abs(grad[i]),reverse=True)[:3]"
        assert s.count(old)==1
        s=s.replace(old,"extra=[140280,140281,140342]\nassert all(0<=i<n and i not in ids for i in extra)")
        old="for eps,cellset in [(1e-3,ids),(1e-2,ids)]:"
        assert s.count(old)==1
        s=s.replace(old,"for eps,cellset in [(1e-3,extra),(1e-2,extra)]:")
        s=s.replace("C2a pre-registered SA adjoint/FD; fail closed on any missing evidence.","C2a diagnostic cells only; original five-cell gate remains unchanged.")
        s=s.replace("# Diagnostic cells are selected after adjoint, never used in five-cell decision.","# Diagnostic IDs were frozen before this run; never used for five-cell decision.")
    elif name=='c2a_solve.qsub':
        for a,b in [('_C2a_third','_C2a_diag'),('C2a_third','C2a_diag'),('c2a_third','c2a_diag'),('C2a_third','C2a_diag'),('20261115_C2a_third','20261115_C2a_diag'),('4470s','3300s'),('4350 - ELAPSED','3150 - ELAPSED')]:
            s=s.replace(a,b)
        s=s.replace('48 slots * at most 4480 seconds < 60 core-hours.','48 slots * at most 3310 seconds < 45 core-hours.')
        s=s.replace('60 core-hour cap','45 core-hour cap')
        s=s.replace('worker target 1.8 h','worker target 1.3 h')
        s=s.replace('#$ -l h_rt=02:00:00','#$ -l h_rt=01:30:00')
        assert 'L26_21_C2a_diag' in s and 'C2a_third' not in s and 'C2a_diag' in s
    else:
        s=s.replace('C2a_third','C2a_diag').replace('c2a_third','c2a_diag')
    p.write_text(s)
# Keep an immutable source comparison for audit.
print('Prepared',*[str(root/n) for n in ('c2a_solve.qsub','c2a_driver.py','c2a_worker.sh')],sep='\n')
