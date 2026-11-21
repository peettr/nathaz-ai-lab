"""Bounded CPU interface check only; synthetic ~2k-node P1 Poisson."""
import json, os, sys, time, traceback
from pathlib import Path
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0')
sys.path[:0]=[str(ROOT/'L0f'), str(ROOT/'repo'), str(ROOT)]
import l0b_worker as w
from l0f_compat_v2 import apply
classes=apply()
import numpy as np
import torch
from skfem import MeshTri,Basis,ElementTriP1,asm, BilinearForm,LinearForm
from skfem.helpers import dot,grad
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import cg,LinearOperator,spsolve_triangular
from scipy.sparse import tril
import l0b_worker as w
@BilinearForm
def stiffness(u,v,_): return dot(grad(u),grad(v))
@LinearForm
def force(v,_): return v
start=time.perf_counter()
try:
    mesh=MeshTri.init_tensor(np.linspace(0,1,48),np.linspace(0,1,48))
    basis=Basis(mesh,ElementTriP1())
    interior=np.setdiff1d(np.arange(basis.N),basis.get_dofs().all())
    A=asm(stiffness,basis).tocsr()[interior][:,interior].tocsr()
    b=np.asarray(asm(force,basis))[interior]
    data=w.graph(A,b,'cpu')
    model=w.model_new().cpu()
    optimizer=torch.optim.AdamW(model.parameters())
    value=w.forward_backward(model,data,optimizer)
    with torch.no_grad(): L,_,_=model(data)
    L=L.coalesce(); idx=L.indices().numpy(); vals=L.values().numpy()
    lower=csr_matrix((vals,(idx[0],idx[1])),shape=A.shape).astype(np.float64)
    lower.sum_duplicates(); lower.sort_indices()
    def pre(v): return spsolve_triangular(lower.T.tocsr(),spsolve_triangular(lower,v,lower=True),lower=False)
    its=[0]
    x,info=cg(A,b,M=LinearOperator(A.shape,matvec=pre,dtype=np.float64),rtol=1e-6,atol=0,maxiter=1000,callback=lambda _:its.__setitem__(0,its[0]+1))
    outcome={'status':'ok','classes':classes,'n':A.shape[0],'nnz':A.nnz,'loss':value,'cg_iterations':its[0],'cg_info':int(info),'relative_residual':float(np.linalg.norm(b-A@x)/np.linalg.norm(b)),'elapsed_s':time.perf_counter()-start}
except Exception as exc:
    outcome={'status':'error','classes':classes,'error':repr(exc),'traceback':traceback.format_exc()[-4000:],'elapsed_s':time.perf_counter()-start}
print('L0F_DRYRUN',json.dumps(outcome),flush=True)
if outcome['status']!='ok' or outcome['cg_info']!=0: raise SystemExit(2)
