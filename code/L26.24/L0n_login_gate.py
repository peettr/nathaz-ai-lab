import sys,time,json
R='/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0'
sys.path[:0]=[R+'/L0n',R+'/L0m/vendor',R+'/repo',R+'/L0m']
import numpy as np, torch
from l0n_generate_v2 import make_sample
from skfem import MeshTri,Basis,ElementTriP1,asm
from skfem.models.poisson import laplace,unit_load
from torch_geometric.data import Data
import types
numml=types.ModuleType('numml');sparse=types.ModuleType('numml.sparse');numml.sparse=sparse
sys.modules['numml']=numml;sys.modules['numml.sparse']=sparse
from neuralif.models import NeuralIF
from l0i_compat import apply
from l0i_sparse_loss import hutchinson_eq7
start=time.monotonic();rows=[]
for seed in range(1300000,1300005):
 try:
  A,b,m=make_sample(seed,2)
  rows.append(dict(seed=seed,status='accepted',n=m['n'],nnz=m['nnz'],min_angle=m['min_angle_deg'],triangles=m['triangles']))
 except ValueError as e:
  rows.append(dict(seed=seed,status='rejected',reason=str(e)))
 print('POLYGON',json.dumps(rows[-1]),flush=True)
# Interface-only tiny case, not a training benchmark. No external weights.
mesh=MeshTri.init_sqsymmetric().refined(4)
basis=Basis(mesh,ElementTriP1());interior=np.setdiff1d(np.arange(basis.N),basis.get_dofs().all())
A=asm(laplace,basis).tocsr()[interior][:,interior].tocoo();b=np.asarray(asm(unit_load,basis))[interior]
apply();torch.manual_seed(42)
model=NeuralIF(latent_size=8,message_passing_steps=3,skip_connections=True,augment_nodes=True,global_features=0,decode_nodes=False,normalize_diag=False,activation='relu',aggregate=None,graph_norm=False,two_hop=False,edge_features=1,normalize=False)
opt=torch.optim.AdamW(model.parameters());losses=[]
for step in range(20):
 d=Data(x=torch.tensor(b.copy(),dtype=torch.float32).view(-1,1),edge_index=torch.tensor(np.stack([A.row,A.col]).copy(),dtype=torch.long),edge_attr=torch.tensor(A.data.copy(),dtype=torch.float32).view(-1,1))
 output,_,_=model(d);torch.manual_seed(123);v=hutchinson_eq7(output,d)
 assert torch.isfinite(v).item(),f'nonfinite loss at {step}'
 v.backward();assert all(torch.isfinite(p.grad).all().item() for p in model.parameters() if p.grad is not None)
 torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);opt.step();opt.zero_grad(set_to_none=True)
 losses.append(float(v.detach()))
print('TRAIN20',json.dumps(dict(n=len(interior),nnz=A.nnz,losses=losses,first=losses[0],last=losses[-1],elapsed_seconds=time.monotonic()-start)),flush=True)
