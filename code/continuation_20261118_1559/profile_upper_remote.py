#!/usr/bin/env python3
"""Recover k=48..52 only, while the owned T15 VM remains active."""
import hashlib,json,pathlib,sys,time
import numpy as np
sys.path.insert(0,'/content')
from remote_worker_run2 import vtk_map
C=pathlib.Path('/content/t15');O=C/'out'
for label in ('WM_s107','WM_s108','WM_s109','K3_s107'):
 while not (O/(label+'_thin.npz.sha256')).is_file():
  if (O/'run.failed').exists() or time.time()>json.loads(pathlib.Path('/content/t15_budget.json').read_text())['work_deadline']-300:sys.exit('upstream failed or deadline '+label)
  time.sleep(3)
 vpaths=list((C/('case_'+label)/'RESULTS/vtk').glob('*_avg-*.vtk'))
 if len(vpaths)!=1:sys.exit('ambiguous VTK '+label)
 v=vtk_map(vpaths[0]);u=np.asarray(v['fields']['u_avg'],dtype='<f4');fluid=np.asarray(v['fields']['fluid'],dtype='<f4')
 k0=48;k1=54
 if u.shape[0]<k1 or u.shape[:3]!=fluid.shape:sys.exit('VTK shape '+label)
 p=O/(label+'_profile_upper.npz')
 hv=hashlib.sha256()
 with vpaths[0].open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):hv.update(b)
 with p.open('xb') as f:np.savez_compressed(f,u_avg=u[k0:k1],fluid=fluid[k0:k1],metadata=json.dumps({'label':label,'k_start':k0,'k_end_exclusive':k1,'origin':v['origin'],'spacing':v['spacing'],'source_vtk_sha256':hv.hexdigest()}))
 h=hashlib.sha256(p.read_bytes()).hexdigest();(O/(p.name+'.sha256')).open('x').write(h+'\n');print('UPPER_READY',label,p.name,h,flush=True)
