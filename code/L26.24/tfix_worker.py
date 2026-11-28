"""Tfix: five immutable later corr-2 systems, same B1/B2/L1 kernels; only Ta target corrected."""
import csv, json, os, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))  # -I omits script directory
import numpy as np
from scipy.sparse import load_npz
import baseline_B1_worker as b1
import baseline_B2_worker as b2
import l1b_cpu as l1

ROOT = Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/Tfix')
SOURCE = l1.SOURCE
L1D = Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/L1d')
NAMES = [f'PresCorr-{i}-2' for i in range(220182, 220187)]
FIELDS = ['system','method','target','rep','initial_residual','target_residual','setup_seconds','inference_seconds','cg_seconds','total_seconds','iterations','achieved_residual','status','source']

def run():
    assert all(os.environ.get(k) == '1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
    manifest = json.loads((L1D/'infer/out/manifest.json').read_text())
    entries = {e['system']:e for e in manifest['factors']}
    assert len(entries)==20 and set(NAMES)<=set(entries)
    old = {r['system']:r for r in csv.DictReader((ROOT/'l1_timing_original.csv').open()) if r['target']=='Ta' and r['rep']=='0'}
    assert set(NAMES)==set(old)
    out = ROOT/'out'; out.mkdir(exist_ok=False)
    with (out/'ta_corr2_fix.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader()
        for name in NAMES:
            folder=SOURCE/name
            assert folder.is_dir()
            A,b,x0,meta,norm,initial=l1.load_system(folder)
            assert name.endswith('-2') and meta['is_final'] is True
            target=max(1e-6,.05*initial)
            assert abs(float(old[name]['initial_residual'])-initial)<1e-10
            for method, fn in [('B1',b1.run),('B2',b2.run)]:
                report=fn(folder,'Ta',5)
                assert abs(report['initial_residual']-initial)<1e-10 and abs(report['target_residual']-target)<1e-10
                for item in report['results']:
                    row=dict(system=name,method=method,target='Ta',rep=item['repetition'],initial_residual=initial,target_residual=target,setup_seconds=item['setup_seconds'],inference_seconds=0,cg_seconds=item['solve_seconds'],total_seconds=item['total_seconds'],iterations=item['iterations'],achieved_residual=item['achieved_residual'],status=item['status'],source='D1b later exported system')
                    assert row['status'] in ('converged','initial_meets_target') and row['achieved_residual']<=target
                    writer.writerow(row);f.flush()
            entry=entries[name]; scale=float(entry['scale'])
            facroot = L1D/'gpu/out' if name=='PresCorr-220182-1' else L1D/'infer/out'
            L=load_npz(facroot/entry['factor_file']).tocsr().astype(np.float64)
            assert L.shape==A.shape and np.isfinite(L.data).all() and np.all(L.diagonal()>0)
            L.data /= np.sqrt(scale)  # identical to l1d_cpu.py:36
            for rep in range(5):
                start=time.perf_counter(); it,r,status=l1.solve(A,b,x0,norm,target,L); seconds=time.perf_counter()-start
                inference=float(entry['inference_seconds_reps'][rep])
                row=dict(system=name,method='L1',target='Ta',rep=rep,initial_residual=initial,target_residual=target,setup_seconds=0,inference_seconds=inference,cg_seconds=seconds,total_seconds=inference+seconds,iterations=it,achieved_residual=r,status=status,source='D1b later exported system; L1d frozen factor')
                assert status in ('converged','initial_meets_target') and r<=target
                writer.writerow(row);f.flush()
            print('TFIX_SYSTEM_COMPLETE',name,initial,target,flush=True)
    print('TFIX_COMPLETE',flush=True)

if __name__=='__main__':
    if '--dry-run' in sys.argv:
        from scipy.sparse import csr_matrix,tril
        A=csr_matrix([[4.,-1.],[-1.,4.]])
        lower=tril(A).tocsr();values=np.empty_like(lower.data)
        assert b2.lib.ic0_factor(2,lower.indptr,lower.indices,np.ascontiguousarray(lower.data),values)==0
        lower.data=values
        it,r,st=l1.solve(A,np.ones(2),np.zeros(2),2.,1e-6,lower)
        assert st=='converged';print('TFIX_DRY_PASS',it,r)
    else:run()
