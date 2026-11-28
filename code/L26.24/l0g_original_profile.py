"""Diagnose original loss sparse backward allocations on tiny graph only."""
import json, os, resource, sys, types
import numpy as np
root='/groups/kareem/[用户]/L26_24_LINSYS_20261115_L0'
sys.path[:0]=[root+'/L0f',root+'/repo',root]
numml=types.ModuleType('numml'); sparse=types.ModuleType('numml.sparse'); numml.sparse=sparse
sys.modules['numml']=numml;sys.modules['numml.sparse']=sparse
import torch
from scipy.sparse import diags, kron, eye
from l0f_compat_v2 import apply
apply()
from l0b_worker import graph,model_new
from neuralif.loss import loss
n=46; one=diags([-np.ones(n-1),4*np.ones(n),-np.ones(n-1)],[-1,0,1],format='csr')
A=kron(eye(n,format='csr'),one)+kron(diags([-np.ones(n-1),-np.ones(n-1)],[-1,1],shape=(n,n),format='csr'),eye(n,format='csr'))
data=graph(A,np.ones(n*n),'cpu'); model=model_new()
with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU],profile_memory=True,record_shapes=True) as p:
    output,_,_=model(data); objective=loss(output,data,config=None); objective.backward()
rows=[]
for event in p.events():
    if event.cpu_memory_usage>1000000:
        rows.append({'name':event.name,'bytes':event.cpu_memory_usage,'input_shapes':event.input_shapes})
print('ORIGINAL_LOSS_PROFILE',json.dumps({'n':n*n,'nnz':A.nnz,'large_allocations':sorted(rows,key=lambda r:r['bytes'],reverse=True)[:12],'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}),flush=True)
