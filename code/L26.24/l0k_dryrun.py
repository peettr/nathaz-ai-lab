"""Submission gate: exact packaged imports and smallest frozen sample, CPU only."""
import json, sys, time
from pathlib import Path
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0/L0k')
sys.path[:0]=[str(ROOT),str(ROOT.parent/'repo')]
import numpy as np
import torch
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import cg, LinearOperator, spsolve_triangular
import l0k_worker as w
from l0i_generate import make_sample
from l0i_sparse_loss import hutchinson_eq7
from l0i_compat import apply

def main():
    t=time.perf_counter()
    assert w.ROOT==ROOT and len(w.SEED_TABLE['accepted'])==1065
    seed=min(w.SEED_TABLE['accepted'], key=lambda r:r['n'])
    classes=apply()
    A,b,meta=make_sample(seed['seed'],seed['geometry'])
    assert (meta['n'],meta['nnz'])==(seed['n'],seed['nnz'])
    data=w.graph(A,b,'cpu'); model=w.model_new().cpu()
    optimizer=torch.optim.AdamW(model.parameters())
    value=w.forward_backward(model,data,optimizer)
    with torch.no_grad(): L,_,_=model(data)
    L=L.coalesce(); idx=L.indices().numpy(); vals=L.values().numpy()
    lower=csr_matrix((vals,(idx[0],idx[1])),shape=A.shape).astype(np.float64)
    lower.sum_duplicates(); lower.sort_indices()
    def pre(v): return spsolve_triangular(lower.T.tocsr(),spsolve_triangular(lower,v,lower=True),lower=False)
    x,info=cg(A,b,M=LinearOperator(A.shape,matvec=pre,dtype=np.float64),rtol=1e-6,atol=0,maxiter=2)
    result=dict(status='passed',classes=classes,seed=seed,n=meta['n'],nnz=meta['nnz'],loss=value,cg_info=int(info),cg_maxiter=2,elapsed_seconds=time.perf_counter()-t,torch=torch.__version__)
    print('L0I_DRYRUN '+json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__': main()
