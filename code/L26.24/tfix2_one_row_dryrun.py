"""One real corrected Ta row; login-node bounded interface precheck."""
import csv, json, os, sys, time
from pathlib import Path
root=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/Tfix2')
sys.path.insert(0,str(root))
import baseline_B2_worker as b2
old={r['system'] for r in csv.DictReader((root/'l1_timing_original.csv').open()) if r['target']=='Ta' and r['rep']=='0'}
names={f'PresCorr-{i}-2' for i in range(220182,220187)}
assert names<=old and len(old)==20
folder=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_D1b/segments/later/Solving/PresCorr-220182-2')
start=time.perf_counter()
r=b2.run(folder,'Ta',1)
assert len(r['results'])==1 and r['results'][0]['status']=='converged'
out=root/'tfix2_dryrun_one_row.csv'
assert not out.exists()
with out.open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['system','method','target','rep','initial_residual','target_residual','iterations','achieved_residual','total_seconds'])
    w.writeheader(); item=r['results'][0]
    w.writerow(dict(system=r['system'],method='B2',target='Ta',rep=0,initial_residual=r['initial_residual'],target_residual=r['target_residual'],iterations=item['iterations'],achieved_residual=item['achieved_residual'],total_seconds=item['total_seconds']))
print('DRYRUN_ONE_ROW_PASS',out,'elapsed',time.perf_counter()-start,'target',r['target_residual'])
