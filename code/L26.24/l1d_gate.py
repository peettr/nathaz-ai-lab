"""L1d held-out first-system gate; no full-batch CG if >650 iterations."""
import json, os, sys, time, traceback
from pathlib import Path
import numpy as np
from scipy.sparse import load_npz, tril
sys.path.insert(0,str(Path(__file__).resolve().parent))
import l1b_cpu as cpu
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/L1d')
OUT=ROOT/'gate'/'out'
NAME='PresCorr-220182-1'
def run(dry=False):
    if dry:
        from scipy.sparse import csr_matrix
        A=csr_matrix([[4.,-1.],[-1.,4.]])
        L=tril(A,format='csr');L.data=np.array([2.,-.5, np.sqrt(3.75)])
        n,r,st=cpu.solve(A,np.ones(2),np.zeros(2),2.,.05,L,limit=650)
        assert st=='converged'; print('L1D_GATE_DRY_PASS',n,r);return
    report=json.loads((ROOT/'gpu/out/l1d_train.json').read_text())
    assert report['status']=='single_factor_ready' and report['epochs_completed']==50
    entry=report['factors'][0];assert entry['system']==NAME
    A,b,x0,meta,factor,initial=cpu.load_system(cpu.SOURCE/NAME)
    s=float(entry['scale']);L=load_npz(ROOT/'gpu/out'/entry['factor_file']).tocsr().astype(np.float64)
    assert A.shape==L.shape and np.isfinite(L.data).all() and (L.diagonal()>0).all() and s>0
    diag=A.diagonal();diagl=L.diagonal()
    rng=np.random.default_rng(20261116);x=rng.standard_normal(A.shape[0]);x/=np.linalg.norm(x)
    approximate=L@(L.T@x);actual=s*(A@x)
    ratio=float(np.linalg.norm(approximate-actual)/np.linalg.norm(actual))
    # L/sqrt(s) factors the original operator A; the triangular solve applies s M^-1.
    Lorig=L.copy();Lorig.data/=np.sqrt(s)
    tol=1e-6 if meta['is_final'] else max(1e-6,.05*initial)
    start=time.perf_counter();it,res,status=cpu.solve(A,b,x0,factor,tol,Lorig,limit=650)
    result={'system':NAME,'scale':s,'diag_A_min':float(diag.min()),'diag_A_mean':float(diag.mean()),'diag_A_max':float(diag.max()),'diag_L_min':float(diagl.min()),'diag_L_max':float(diagl.max()),'diag_ratio_median':float(np.median(diagl/np.sqrt(s*diag))),'approximation_relative_l2':ratio,'initial_residual':initial,'target':tol,'iterations':it,'achieved_residual':res,'status':status,'seconds':time.perf_counter()-start,'ic0_reference_iterations':65,'pass':status=='converged' and it<=650,'applied_preconditioner':'s*L^-T L^-1'}
    OUT.mkdir(parents=True,exist_ok=False)
    with (OUT/'gate.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print('L1D_GATE',json.dumps(result),flush=True)
if __name__=='__main__':
    try:run('--dry-run' in sys.argv)
    except BaseException:
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'error.txt').write_text(traceback.format_exc());raise
