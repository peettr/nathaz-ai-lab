"""L1 held-out NeuralIF+CG with B2 native triangular kernel and OpenFOAM norm."""
import csv, ctypes as c, json, os, re, sys, time, traceback
from pathlib import Path
import numpy as np
from scipy.io import mmread
from scipy.sparse import load_npz, tril
from scipy.sparse.linalg import LinearOperator,cg
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1')
SOURCE=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_D1b/segments/later/Solving')
B2=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_B/B2/rows')
LIB=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_B/libic0_B2.so')
I=np.ctypeslib.ndpointer(dtype=np.int32,flags='C_CONTIGUOUS');D=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
lib=c.CDLL(str(LIB));lib.ic0_factor.argtypes=[c.c_int,I,I,D,D];lib.ic0_factor.restype=c.c_int
lib.ic0_apply.argtypes=[c.c_int,I,I,D,I,I,D,D,D,D];lib.ic0_apply.restype=None
class Reached(Exception):
    def __init__(self,x,residual,iterations):self.x,self.residual,self.iterations=x,residual,iterations

def norm(A,b,x,factor):return float(np.abs(b-A@x).sum()/factor)
def solve(A,b,x0,factor,tol,L,limit=10000):
    U=L.T.tocsr();U.sort_indices();work=np.empty_like(b)
    def apply(v):
        out=np.empty_like(v)
        lib.ic0_apply(A.shape[0],L.indptr,L.indices,L.data,U.indptr,U.indices,U.data,np.ascontiguousarray(v),work,out)
        return out
    M=LinearOperator(A.shape,matvec=apply,dtype=np.float64); counter=[0]
    def monitor(x):
        counter[0]+=1
        r=norm(A,b,x,factor)
        if r<=tol:raise Reached(x.copy(),r,counter[0])
    if norm(A,b,x0,factor)<=tol:return 0,norm(A,b,x0,factor),'initial_meets_target'
    try:
        x,info=cg(A,b,x0=x0,M=M,rtol=1e-14,atol=0,maxiter=limit,callback=monitor)
        res=norm(A,b,x,factor);return counter[0],res,('converged' if res<=tol else 'not_met_cg_info_'+str(info))
    except Reached as done:return done.iterations,done.residual,'converged'

def load_system(d):
    A=-mmread(str(d/'A.mtx.gz')).tocsr().astype(np.float64);A.sum_duplicates();A.sort_indices()
    b=-np.load(d/'b.npy');x0=np.load(d/'x_initial.npy');meta=json.loads((d/'meta.json').read_text())
    ref=[邮箱](x0,np.mean(x0));factor=float(np.abs(A@x0-ref).sum()+np.abs(b-ref).sum()+1e-20)
    initial=norm(A,b,x0,factor)
    return A,b,x0,meta,factor,initial

def run():
    assert all(os.getenv(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
    manifest=json.loads((ROOT/'gpu/out/l1_train.json').read_text())
    assert manifest['status']=='complete' and len(manifest['factors'])==20
    factors={p['system']:p for p in manifest['factors']}
    dirs=sorted(SOURCE.glob('PresCorr-*'),key=lambda d:tuple(map(int,re.findall(r'\d+',d.name))))
    assert len(dirs)==20 and set(factors)=={d.name for d in dirs}
    out=ROOT/'cpu/out';out.mkdir(exist_ok=True)
    fields=['system','segment','target','rep','initial_residual','target_residual','inference_seconds','cg_seconds','total_seconds','iterations','achieved_residual','status','factor_nnz','cpu_model','threads']
    b2rows=[];allrows=[]
    csvpath=out/'l1_timing.csv';assert not csvpath.exists()
    with csvpath.open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for d in dirs:
            A,b,x0,meta,factor,initial=load_system(d)
            L=load_npz(ROOT/'gpu/out'/factors[d.name]['factor_file']).tocsr().astype(np.float64);L.sum_duplicates();L.sort_indices()
            assert np.all(np.isfinite(L.data)) and np.all(L.diagonal()>0) and A.shape==L.shape
            for target in ('Ta','Tb'):
                tol=(max(1e-6,.05*initial) if not meta['is_final'] else 1e-6) if target=='Ta' else 1e-8
                for rep in range(5):
                    started=time.perf_counter();it,r,status=solve(A,b,x0,factor,tol,L);secs=time.perf_counter()-started
                    infer=factors[d.name]['inference_seconds_reps'][rep]
                    row=dict(system=d.name,segment='later',target=target,rep=rep,initial_residual=initial,target_residual=tol,inference_seconds=infer,cg_seconds=secs,total_seconds=infer+secs,iterations=it,achieved_residual=r,status=status,factor_nnz=L.nnz,cpu_model=next((v.split(':',1)[1].strip() for v in Path('/proc/cpuinfo').read_text().splitlines() if v.startswith('model name')),'unknown'),threads=1)
                    writer.writerow(row);stream.flush();allrows.append(row)
                    print('L1',d.name,target,rep,it,status,secs,flush=True)
                # IC comparison uses exact same solve function and triangular kernel, once per target.
                Li=tril(A,format='csr');Li.sort_indices();v=np.empty_like(Li.data)
                rc=lib.ic0_factor(A.shape[0],Li.indptr,Li.indices,np.ascontiguousarray(Li.data),v)
                if rc:raise ArithmeticError(f'IC0 breakdown {d.name} row {rc}')
                Li.data=v;it,r,status=solve(A,b,x0,factor,tol,Li)
                original=json.loads((B2/(f'later_{d.name}_{target}.json')).read_text())
                b2it=[int(x['iterations']) for x in original['results']]
                b2rows.append(dict(system=d.name,target=target,ic_iterations=it,b2_iterations=b2it,identical=all(it==x for x in b2it),residual=r,status=status))
            del A,L,b,x0
    with (out/'l1_ic_crosscheck.json').open('x') as f:json.dump({'rows':b2rows,'all_identical':all(x['identical'] for x in b2rows)},f,indent=2)
    from statistics import median
    def quartile(a,q):return float(np.quantile(np.array(a,dtype=float),q))
    summary={'source':'D1b later 20 immutable exported systems, per-system five CG repeats, single measured warmed GPU inference amortized only for measurement (included in EACH total)','targets':{},'ic_same_code_all_identical':all(x['identical'] for x in b2rows),'count':len(allrows),'training_seconds':manifest['train_wall_seconds'],'gpu_peak_bytes':manifest['gpu_peak_bytes']}
    for target in ('Ta','Tb'):
        group=[]
        for d in dirs:
            x=[r for r in allrows if r['system']==d.name and r['target']==target]
            assert len(x)==5
            group.append(median(r['total_seconds'] for r in x))
        med=median(group);summary['targets'][target]={'systems':len(group),'median_seconds':med,'q25_seconds':quartile(group,.25),'q75_seconds':quartile(group,.75),'iqr_seconds':quartile(group,.75)-quartile(group,.25),'converged':sum(r['status']=='converged' or r['status']=='initial_meets_target' for r in allrows if r['target']==target),'threshold_seconds':(.0241 if target=='Ta' else .222),'below_threshold':med<=(.0241 if target=='Ta' else .222)}
    summary['Ta_vs_B1_threshold_seconds']=5.44
    summary['Ta_le_B1_threshold']=summary['targets']['Ta']['median_seconds']<=5.44
    with (out/'l1_summary.json').open('x') as f:json.dump(summary,f,indent=2,allow_nan=False)
    assert len(allrows)==200
    print('L1_CPU_COMPLETE',json.dumps(summary['targets']),flush=True)
if __name__=='__main__':
    if '--dry-run' in sys.argv:
        from scipy.sparse import csr_matrix
        A=csr_matrix(np.array([[4.,-1.,0.],[-1.,4.,-1.],[0.,-1.,4.]]))
        L=tril(A,format='csr');L.sort_indices();v=np.empty_like(L.data)
        assert lib.ic0_factor(3,L.indptr,L.indices,np.ascontiguousarray(L.data),v)==0
        L.data=v;b=np.array([1.,2.,3.]);x0=np.zeros(3)
        it,r,status=solve(A,b,x0,float(np.abs(b).sum()),1e-6,L)
        assert status=='converged' and r<=1e-6
        print('L1_CPU_DRYRUN_PASS',it,r,flush=True);sys.exit(0)
    try:run()
    except BaseException:
        p=ROOT/'cpu/out';p.mkdir(exist_ok=True);(p/'error.txt').write_text(traceback.format_exc());raise
