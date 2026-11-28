"""Login-node bounded interface/memory scale check, not scientific training."""
import json, os, resource, sys, time, types
import numpy as np
root='/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0'
sys.path[:0]=[root+'/L0f',root+'/repo',root,root+'/L0g']
numml=types.ModuleType('numml'); sparse=types.ModuleType('numml.sparse'); numml.sparse=sparse
sys.modules['numml']=numml;sys.modules['numml.sparse']=sparse
import torch
from scipy.sparse import diags, kron, eye
from l0f_compat_v2 import apply
apply()
from l0g_sparse_loss import hutchinson_eq7
from l0b_worker import graph, model_new
n=int(sys.argv[1]); side=int(np.sqrt(n)); n=side*side
t0=time.perf_counter()
one=diags([-np.ones(side-1),4*np.ones(side),-np.ones(side-1)],[-1,0,1],format='csr')
A=kron(eye(side,format='csr'),one)+kron(diags([-np.ones(side-1),-np.ones(side-1)],[-1,1],shape=(side,side),format='csr'),eye(side,format='csr'))
A=A.tocsr(); data=graph(A,np.ones(n), 'cpu'); model=model_new()
output,_,_=model(data); val=hutchinson_eq7(output,data); val.backward()
print('SCALE',json.dumps({'n':n,'nnz':A.nnz,'loss':float(val.detach()),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'seconds':time.perf_counter()-t0}),flush=True)
