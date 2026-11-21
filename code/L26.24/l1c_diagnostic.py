#!/usr/bin/env python3
"""L26.24 L1c: one held-out system; immutable inputs; bounded four-path CG."""
import csv, ctypes as ct, json, os, time, traceback
from pathlib import Path
import numpy as np
from scipy.io import mmread
from scipy.sparse import load_npz, tril
from scipy.sparse.linalg import LinearOperator, cg

SRC=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_D1b/segments/later/Solving/PresCorr-220182-1')
FAC=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/L1b/gpu/out/PresCorr-220182-1.npz')
B2=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_B/B2/rows/later_PresCorr-220182-1_Ta.json')
LIB=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_B/libic0_B2.so')
OUT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/L1c/out')
I=np.ctypeslib.ndpointer(dtype=np.int32,flags='C_CONTIGUOUS')
D=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
lib=ct.CDLL(str(LIB))
lib.ic0_factor.argtypes=[ct.c_int,I,I,D,D];lib.ic0_factor.restype=ct.c_int
lib.ic0_apply.argtypes=[ct.c_int,I,I,D,I,I,D,D,D,D];lib.ic0_apply.restype=None
class StopCG(Exception):
    def __init__(self,why,x): self.why,self.x=why,x.copy()

def norm(A,b,x,f): return float(np.abs(b-A@x).sum()/f)
def op(A,b,x0):
    ref=[邮箱](x0,np.mean(x0));f=float(np.abs(A@x0-ref).sum()+np.abs(b-ref).sum()+1e-20)
    return f,norm(A,b,x0,f)
def apply_for(L):
    U=L.T.tocsr();U.sort_indices();w=np.empty(L.shape[0],dtype=np.float64)
    def act(v):
        out=np.empty_like(v)
        lib.ic0_apply(L.shape[0],L.indptr,L.indices,L.data,U.indptr,U.indices,U.data,np.ascontiguousarray(v),w,out)
        return out
    return act

def solve(name,A,b,x0,report_A,report_b,factor,threshold,L,limit=2000):
    # A,b may be jointly negated, report_A/report_b are original positive SPD convention.
    act=apply_for(L) if L is not None else None
    if act is not None:
        M=LinearOperator(A.shape,matvec=lambda v:(-act(v) if name=='neural_negated' else act(v)),dtype=np.float64)
    else:M=None
    r0=np.linalg.norm(report_b-report_A@x0)
    traces=[];counter=0;started=time.perf_counter()
    def record(k,x):
        r=report_b-report_A@x
        traces.append(dict(method=name,iteration=k,of_residual=float(np.abs(r).sum()/factor),relative_l2=float(np.linalg.norm(r)/r0)))
    record(0,x0)
    def callback(x):
        nonlocal counter
        counter+=1
        if counter%50==0:record(counter,x)
        if np.abs(report_b-report_A@x).sum()/factor<=threshold: raise StopCG('target',x)
    status=''
    try:
        x,info=cg(A,b,x0=x0,M=M,rtol=1e-14,atol=0,maxiter=limit,callback=callback)
        status=f'info_{info}'
    except StopCG as e:x=e.x;status=e.why
    # Last callback may have stopped before sample at 50.
    final=norm(report_A,report_b,x,factor)
    return traces,dict(method=name,iterations=counter,final_residual=final,status=status,seconds=time.perf_counter()-started)

def run(dry=False):
    if dry:
        from scipy.sparse import csr_matrix
        A=csr_matrix([[4.,-1.,0.],[-1.,4.,-1.],[0.,-1.,4.]])
        L=tril(A).tocsr();v=np.empty_like(L.data)
        assert lib.ic0_factor(3,L.indptr,L.indices,np.ascontiguousarray(L.data),v)==0
        L.data=v;f,i=op(A,np.ones(3),np.zeros(3));assert f>0 and i>0
        print('L1C_DRY_PASS',f,i,flush=True);return
    OUT.mkdir(parents=True,exist_ok=False)
    raw=mmread(str(SRC/'A.mtx.gz')).tocsr().astype(np.float64);raw.sum_duplicates();raw.sort_indices()
    rawb=np.load(SRC/'b.npy');A=-raw;b=-rawb;x0=np.load(SRC/'x_initial.npy')
    factor,initial=op(A,b,x0)
    nf=load_npz(FAC).tocsr().astype(np.float64);nf.sum_duplicates();nf.sort_indices()
    lower=tril(A,format='csr');lower.sort_indices();v=np.empty_like(lower.data)
    rc=lib.ic0_factor(A.shape[0],lower.indptr,lower.indices,np.ascontiguousarray(lower.data),v)
    assert rc==0,rc
    lower.data=v
    b2=json.loads(B2.read_text()); b2iters=[int(r['iterations']) for r in b2['results']]
    rng=np.random.default_rng(20261116);x=rng.standard_normal(A.shape[0]);x/=np.linalg.norm(x)
    approx=nf@(nf.T@x);ax=A@x
    approximation=float(np.linalg.norm(approx-ax)/np.linalg.norm(ax))
    print('SIGN',json.dumps(dict(raw_diag=[float(raw.diagonal().min()),float(raw.diagonal().max())],spd_diag=[float(A.diagonal().min()),float(A.diagonal().max())],factor_diag=[float(nf.diagonal().min()),float(nf.diagonal().max())],actual_operator='-exported_A',actual_rhs='-exported_b',factor_approximation=approximation,initial_of_residual=initial,b2_iterations=b2iters)),flush=True)
    # Reproduce precisely B2's initial state and target on the first held-out system.
    meta=json.loads((SRC/'meta.json').read_text()); tol=1e-6 if meta['is_final'] else max(1e-6,.05*initial)
    rows=[];summ=[]
    for name,am,bm,L in [('none',A,b,None),('ic0',A,b,lower),('neural',A,b,nf),('neural_negated',raw,rawb,nf)]:
        trace,s=solve(name,am,bm,x0,A,b,factor,tol,L)
        rows.extend(trace);summ.append(s)
        print('PATH',json.dumps(s),flush=True)
    report=dict(system=SRC.name,n=A.shape[0],nnz=A.nnz,raw_diagonal_min=float(raw.diagonal().min()),raw_diagonal_max=float(raw.diagonal().max()),spd_diagonal_min=float(A.diagonal().min()),spd_diagonal_max=float(A.diagonal().max()),factor_diagonal_min=float(nf.diagonal().min()),factor_diagonal_max=float(nf.diagonal().max()),operator='-exported_A',rhs='-exported_b',negative_variant='exported_A and exported_b; preconditioner -LLt inverse',preconditioner='L^-T(L^-1 r)',initial_of_residual=initial,target_of_residual=tol,norm_factor=factor,b2_iterations=b2iters,ic_matches_b2=(summ[1]['iterations'] in b2iters),factor_approximation_relative_l2=approximation,paths=summ)
    with (OUT/'l1c_summary.json').open('x') as f:json.dump(report,f,indent=2,allow_nan=False)
    with (OUT/'l1c_trace.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['method','iteration','of_residual','relative_l2']);w.writeheader();w.writerows(rows)
    print('L1C_COMPLETE',flush=True)
if __name__=='__main__':
    try:run('--dry-run' in os.sys.argv)
    except BaseException:
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'error.txt').write_text(traceback.format_exc());raise
