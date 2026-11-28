"""Verify the indexed matvec equals repository loss and parameter gradients."""
import json, sys, types
import numpy as np
root='/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0'
sys.path[:0]=[root+'/L0g',root+'/L0f',root+'/repo',root]
numml=types.ModuleType('numml'); sparse=types.ModuleType('numml.sparse'); numml.sparse=sparse
sys.modules['numml']=numml;sys.modules['numml.sparse']=sparse
import torch
from scipy.sparse import diags, kron, eye
from l0f_compat_v2 import apply
apply()
from l0b_worker import graph,model_new
from neuralif.loss import loss
from l0g_sparse_loss import hutchinson_eq7
side=46; n=side*side; I=eye(side,format='csr')
A=kron(I,diags([-np.ones(side-1),4*np.ones(side),-np.ones(side-1)],[-1,0,1],format='csr')) + kron(diags([-np.ones(side-1),-np.ones(side-1)],[-1,1],shape=(side,side),format='csr'),I)
data=graph(A,np.ones(n),'cpu'); model=model_new(); output,_,_=model(data)
torch.manual_seed(991); old=loss(output,data,config=None); oldgrad=torch.autograd.grad(old,tuple(model.parameters()),retain_graph=True,allow_unused=True)
torch.manual_seed(991); new=hutchinson_eq7(output,data); newgrad=torch.autograd.grad(new,tuple(model.parameters()),allow_unused=True)
assert all((a is None)==(b is None) for a,b in zip(oldgrad,newgrad))
errors=[(a-b).abs().max().item() for a,b in zip(oldgrad,newgrad) if a is not None]
relative=max(errors)/(max(g.abs().max().item() for g in oldgrad if g is not None)+1e-30)
print('EQUIVALENCE',json.dumps({'n':n,'old_loss':float(old),'new_loss':float(new),'loss_relative_diff':float(abs(old-new)/(abs(old)+1e-30)),'gradient_max_relative_diff':relative}),flush=True)
if float(abs(old-new)/(abs(old)+1e-30))>1e-5 or relative>1e-4: raise SystemExit(2)
