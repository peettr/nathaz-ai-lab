"""Tfix3: one method per original environment; five corrected later corr2 systems."""
import csv, json, os, sys, time
from pathlib import Path
import numpy as np
from scipy.sparse import load_npz
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/Tfix3')
SOURCE=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_D1b/segments/later/Solving')
L1D=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/L1d')
NAMES=[f'PresCorr-{i}-2' for i in range(220182,220187)]
FIELDS=['system','method','target','rep','initial_residual','target_residual','setup_seconds','inference_seconds','cg_seconds','total_seconds','iterations','achieved_residual','status','source']

def run(method, one=False):
    assert method in ('B1','B2','L1')
    assert all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
    old={r['system']:r for r in csv.DictReader((ROOT/'l1_timing_original.csv').open()) if r['target']=='Ta' and r['rep']=='0'}
    assert set(NAMES)<=set(old) and len(old)==20
    manifest=json.loads((L1D/'infer/out/manifest.json').read_text())
    entries={e['system']:e for e in manifest['factors']}
    assert len(entries)==20 and set(NAMES)<=set(entries)
    sys.path.insert(0,str(ROOT))
    if method=='B1':import baseline_B1_worker as worker
    if method=='B2':import baseline_B2_worker as worker
    if method=='L1':import l1b_cpu as worker
    out=ROOT/('dryrun' if one else 'out')
    out.mkdir(exist_ok=True)
    dest=out/f'{method.lower()}.csv'
    assert not dest.exists(),dest
    with dest.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader()
        for name in NAMES[:1] if one else NAMES:
            folder=SOURCE/name
            assert folder.is_dir()
            if method in ('B1','B2'):
                report=worker.run(folder,'Ta',1 if one else 5)
                initial=float(report['initial_residual']);target=max(1e-6,.05*initial)
                assert abs(float(report['target_residual'])-target)<1e-10
                items=report['results']
                for item in items:
                    row=dict(system=name,method=method,target='Ta',rep=item['repetition'],initial_residual=initial,target_residual=target,setup_seconds=item['setup_seconds'],inference_seconds=0,cg_seconds=item['solve_seconds'],total_seconds=item['total_seconds'],iterations=item['iterations'],achieved_residual=item['achieved_residual'],status=item['status'],source='D1b later exported system')
                    assert row['status'] in ('converged','initial_meets_target') and float(row['achieved_residual'])<=target
                    w.writerow(row);f.flush()
            else:
                A,b,x0,meta,norm,initial=worker.load_system(folder)
                target=max(1e-6,.05*initial)
                entry=entries[name];scale=float(entry['scale'])
                L=load_npz(L1D/'infer/out'/entry['factor_file']).tocsr().astype(np.float64)
                assert L.shape==A.shape and np.isfinite(L.data).all() and np.all(L.diagonal()>0)
                L.data/=np.sqrt(scale)
                for rep in range(1 if one else 5):
                    start=time.perf_counter(); it,r,status=worker.solve(A,b,x0,norm,target,L);secs=time.perf_counter()-start
                    infer=float(entry['inference_seconds_reps'][rep])
                    row=dict(system=name,method='L1',target='Ta',rep=rep,initial_residual=initial,target_residual=target,setup_seconds=0,inference_seconds=infer,cg_seconds=secs,total_seconds=infer+secs,iterations=it,achieved_residual=r,status=status,source='D1b later exported system; L1d frozen factor')
                    assert status in ('converged','initial_meets_target') and r<=target
                    w.writerow(row);f.flush()
            assert abs(float(old[name]['initial_residual'])-initial)<1e-10
            print('TFIX3_SYSTEM',method,name,initial,target,flush=True)
    count=sum(1 for _ in csv.DictReader(dest.open()))
    assert count==(1 if one else 25),(method,count)
    print('TFIX3_COMPLETE',method,count,dest,flush=True)

if __name__=='__main__':
    assert len(sys.argv) in (2,3)
    run(sys.argv[1],len(sys.argv)==3 and sys.argv[2]=='--one')
