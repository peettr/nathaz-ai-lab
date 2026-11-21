"""L0l read-only checkpoint evaluation, allocated A10 only; no model training."""
import ctypes as C, json, os, time, resource, sys, types
from pathlib import Path
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0/L0l')
numml=types.ModuleType('numml'); sparse=types.ModuleType('numml.sparse')
numml.sparse=sparse; sys.modules['numml']=numml; sys.modules['numml.sparse']=sparse
sys.path[:0]=[str(ROOT),str(ROOT.parent/'repo')]
import numpy as np
import torch
from scipy.sparse import csr_matrix, tril
from scipy.sparse.linalg import cg, LinearOperator, spsolve_triangular
from l0i_compat import apply as apply_compat
apply_compat()
from neuralif.models import NeuralIF
from l0i_generate import make_sample
from torch_geometric.data import Data
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0/L0l')
OUT=ROOT/'gpu'/'out'
assert os.getenv('JOB_ID') or os.getenv('SGE_JOB_ID')
assert torch.cuda.is_available() and torch.cuda.device_count()==1
OUT.mkdir(parents=True,exist_ok=True)
SEEDS=json.loads((ROOT/'accepted_seeds.json').read_text())
ROWS=[r for r in SEEDS['accepted'] if r['split']=='test']
assert len(ROWS)==300
lib=C.CDLL('/groups/kareem/[用户]/L26_24_LINSYS_20261115_B/libic0_B2.so')
I=np.ctypeslib.ndpointer(dtype=np.int32,flags='C_CONTIGUOUS')
D=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
lib.ic0_factor.argtypes=[C.c_int,I,I,D,D];lib.ic0_factor.restype=C.c_int

def factor(A):
    L=tril(A,format='csr');L.sort_indices();f=np.empty_like(L.data)
    status=lib.ic0_factor(A.shape[0],L.indptr,L.indices,np.ascontiguousarray(L.data),f)
    if status: raise RuntimeError(f'IC0 breakdown at {status}')
    L.data=f
    return L

def solve(A,b,L):
    M=None
    if L is not None:
        LT=L.T.tocsr()
        M=LinearOperator(A.shape,dtype=np.float64,matvec=lambda v:spsolve_triangular(LT,spsolve_triangular(L,v,lower=True),lower=False))
    count=[0]
    x,info=cg(A,b,rtol=1e-6,atol=0,maxiter=10000,M=M,callback=lambda _:count.__setitem__(0,count[0]+1))
    return {'iterations':count[0],'converged':info==0,'info':int(info),
            'true_relative_residual':float(np.linalg.norm(b-A@x)/np.linalg.norm(b))}

def graph(A,b):
    coo=A.tocoo()
    edges=np.stack((coo.row,coo.col)).astype(np.int64)
    return Data(x=torch.from_numpy(np.asarray(b,dtype=np.float32).copy()).view(-1,1).cuda(),
                edge_index=torch.from_numpy(edges.copy()).cuda(),
                edge_attr=torch.from_numpy(coo.data.astype(np.float32,copy=True)).view(-1,1).cuda())

def model_new():
    return NeuralIF(latent_size=8,message_passing_steps=3,skip_connections=True,
                    augment_nodes=True,global_features=0,decode_nodes=False,
                    normalize_diag=False,activation='relu',aggregate=None,
                    graph_norm=False,two_hop=False,edge_features=1,normalize=False)

def stats(rows,key):
    vals=[r[key]['iterations'] for r in rows if r[key]['converged']]
    return {'converged':len(vals),'total':len(rows),'mean_all':float(np.mean(vals)) if len(vals)==len(rows) else None,
            'median_all':float(np.median(vals)) if len(vals)==len(rows) else None,
            'mean_converged_only':float(np.mean(vals)) if vals else None,
            'median_converged_only':float(np.median(vals)) if vals else None}

def main():
    model=model_new().cuda()
    state=torch.load(ROOT/'own_model.pt',map_location='cpu',weights_only=True)
    model.load_state_dict(state,strict=True);model.eval()
    started=time.monotonic();rows=[];errors=[]
    for j,r in enumerate(ROWS):
        A,b,meta=make_sample(r['seed'],r['geometry'])
        data=graph(A,b)
        with torch.no_grad(): L,_,_=model(data)
        L=L.coalesce().cpu();indices=L.indices().numpy();values=L.values().numpy()
        learned=csr_matrix((values,(indices[0],indices[1])),shape=A.shape).astype(np.float64)
        learned.sum_duplicates();learned.sort_indices()
        ic=factor(A)
        result={'index':j,'geometry':r['geometry'],'seed':r['seed'],'n':A.shape[0],
                'nnz':A.nnz,'neuralif':solve(A,b,learned),'ic0':solve(A,b,ic),'none':solve(A,b,None)}
        if j<20:
            # Sparse matmul; no dense n*n allocation.
            for name,M in [('neuralif',learned),('ic0',ic)]:
                delta=([邮箱]).tocsr()
                result[name+'_relative_factor_frobenius']=float(np.sqrt(np.dot(delta.data,delta.data)/np.dot(A.data,A.data)))
            errors.append(result)
        rows.append(result)
        with (OUT/'per_case.jsonl').open('a') as f: f.write(json.dumps(result,allow_nan=False)+'\n')
        if (j+1)%10==0: print('EVAL',j+1,'elapsed_s',time.monotonic()-started,flush=True)
        if time.monotonic()-started>6900:
            with (OUT/'incomplete.json').open('x') as f: json.dump({'reason':'time_gate','completed':len(rows)},f)
            return
    report={'status':'complete','source_checkpoint_sha256':'91720b18fba3a67f86fc201eb3dc25d1bea76627b1a8423293b665c076ec2032',
            'eval_seconds':time.monotonic()-started,'gpu_peak_bytes':torch.cuda.max_memory_allocated(),
            'residual':'scipy cg rtol=1e-6 atol=0, x0=0; ||r||/||b||',
            'neuralif':stats(rows,'neuralif'),'ic0':stats(rows,'ic0'),'none':stats(rows,'none'),
            'relative_factor_frobenius_first20':errors,
            'loss_curve':'not recorded in original L0k training log; checkpoint cannot reconstruct historical epoch losses'}
    with (OUT/'reeval_summary.json').open('x') as f:json.dump(report,f,indent=2,allow_nan=False)
if __name__=='__main__':main()
