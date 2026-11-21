#!/usr/bin/env python3
"""Remote GPU worker: only E_s102_off; host SHA ACK required."""
import pathlib,json,hashlib,tarfile,subprocess,os,time,traceback,shutil,csv,math,itertools
import numpy as np
from remote_worker_run2 import vtk_map
R=pathlib.Path('/content');S=R/'stage';O=R/'t5_out'
CASES=['E_s102_off']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def sampled(v,p):
 dx=v['spacing'][0];assert v['dims']==(500,500,270) and v['origin']==(0.,0.,-20.) and v['spacing']==(1.,1.,1.)
 # Exact T2c/T2d B2u horizontal translation and real wall 2 m: wall plane 0.5 m, VTK z=2.5 m.
 xyz=(p['xls_xy'][0]+1010.50008-760+1.,p['xls_xy'][1]+1000.60004-750+1.,2.5)
 q=[(a-b)/dx for a,b in zip(xyz,v['origin'])];idx=[math.floor(a) for a in q];w=[a-i for a,i in zip(q,idx)]
 assert all(0<=i<n-1 for i,n in zip(idx,v['dims'])),(xyz,idx)
 su=solid=0.;corners=0
 for dz,dy,di in itertools.product((0,1),repeat=3):
  weight=(w[0] if di else 1-w[0])*(w[1] if dy else 1-w[1])*(w[2] if dz else 1-w[2]);k,j,i=idx[2]+dz,idx[1]+dy,idx[0]+di
  val=float(v['fields']['speed_mean'][k,j,i]);fluid=float(v['fields']['fluid'][k,j,i])>.5
  assert math.isfinite(val)
  su+=weight*val;solid+=weight*(not fluid);corners+=int(fluid)
 return {'Su':su,'Su_ratio':su/3.9286416,'xyz_m':xyz,'fluid_corners':corners,'solid_weight':solid}
def run():
 O.mkdir(exist_ok=False)
 archive=R/'stage_t5.tar.gz';assert sha(archive)==json.loads((R/'archive.json').read_text())['sha256']
 with tarfile.open(archive) as t:
  for m in t.getmembers():assert (m.name=='stage' or m.name.startswith('stage/')) and '..' not in pathlib.PurePath(m.name).parts and (m.isfile() or m.isdir()),m.name
  assert not S.exists();t.extractall(R,filter='data')
 man=json.loads((S/'manifest.json').read_text());ref=json.loads((R/'B2u_reference_points.json').read_text());assert len(ref['rows'])==80 and ref['uref']==3.9286416
 deadline=float(os.environ['T5_DEADLINE'])
 for mode in ('off',):
  src=S/f'FluidX3D_{mode}'
  for n,h in man['source'][mode].items():assert sha(src/'src'/n)==h
  with (O/f'{mode}_build.log').open('x') as f:p=subprocess.run(['make','Linux','-j8'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=1200)
  print('BUILD',mode,p.returncode,flush=True)
  if p.returncode:raise RuntimeError('build failure '+mode)
 for label in CASES:
  mode=man['cases'][label]['variant'];src=S/f'FluidX3D_{mode}';base=R/'t5_cases'/label;assert not base.exists()
  shutil.copytree(S/'cases'/label,base)
  conf=base/'conf.luwpf';assert sha(conf)==man['cases'][label]['config_sha256']
  # Pre-launch budget checks are also enforced by the host controller.
  if time.time()+1600>deadline:raise RuntimeError('remaining CU window insufficient for '+label)
  env={**os.environ,'LD_LIBRARY_PATH':str(src/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH',''),'LUW_GROUND_MIX_A':'0','LUW_CAPTURE_CL':str(O/f'{label}_actual_opencl.cl')}
  print('START',label,'remaining_s',round(deadline-time.time()),flush=True)
  start=time.time()
  with (O/f'{label}_solver.log').open('x') as f:p=subprocess.run([str(src/'bin/FluidX3D'),str(conf)],cwd=base,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=min(5400,max(60,deadline-time.time()-450)))
  (O/f'{label}_exit.json').write_text(json.dumps({'solver_exit':p.returncode,'elapsed_s':time.time()-start})+'\n')
  print('SOLVER_EXIT',label,p.returncode,flush=True)
  if p.returncode:raise RuntimeError('solver failed '+label)
  vtk=list((base/'RESULTS/vtk').glob('*_avg-*.vtk'));assert len(vtk)==1,(label,vtk)
  v=vtk_map(vtk[0]);assert v['dims']==(500,500,270) and v['origin']==(0.,0.,-20.)
  # k=20..46 covers centre heights 0..26 m; store all x/y and native fluid flags.
  k0=20;k1=47
  with (O/f'{label}_thin.npz').open('xb') as f:np.savez_compressed(f,u_avg=np.asarray(v['fields']['u_avg'][k0:k1],dtype='<f4'),fluid=np.asarray(v['fields']['fluid'][k0:k1],dtype='<f4'),speed_mean=np.asarray(v['fields']['speed_mean'][k0:k1],dtype='<f4'),metadata=json.dumps({'k_start':k0,'k_end_exclusive':k1,'dims':v['dims'],'origin':v['origin'],'vtk_sha256':sha(vtk[0]),'config_sha256':sha(conf)}))
  rows=[{'id':int(p['id']),'obs':float(p['after']),**sampled(v,p)} for p in ref['rows']]
  assert len({p['id'] for p in rows})==80 and all(math.isfinite(p['Su_ratio']) for p in rows)
  (O/f'{label}_points80.json').write_text(json.dumps({'label':label,'uref':ref['uref'],'rows':rows,'source_vtk_sha256':sha(vtk[0]),'sample_height_above_wall_m':2.0,'vtk_label_z_m':2.5},indent=2)+'\n')
  for ext in ('thin.npz','points80.json'):
   f=O/f'{label}_{ext}';(O/f'{label}_{ext}.sha256').write_text(sha(f)+'\n')
  for name in ('ground_eligibility.csv','ground_excluded.csv','city_stability.csv','wall_tau_actual.csv'):
   p=base/'RESULTS'/name
   if p.is_file():shutil.copyfile(p,O/f'{label}_{name}')
  cl=O/f'{label}_actual_opencl.cl';assert cl.is_file()
  print('READY',label,sha(O/f'{label}_thin.npz'),sha(O/f'{label}_points80.json'),flush=True)
  ack=O/f'{label}.ack';expected=sha(O/f'{label}_thin.npz')+' '+sha(O/f'{label}_points80.json')
  while not ack.exists():
   if time.time()+500>deadline:raise RuntimeError('ACK deadline '+label)
   time.sleep(10)
  assert ack.read_text().strip()==expected,(label,'ACK mismatch')
  print('HOST_VERIFIED',label,flush=True)
 (O/'run.done').write_text('E_s102_off complete\n');print('ALL_DONE',flush=True)
if __name__=='__main__':
 try:run()
 except BaseException:
  traceback.print_exc();O.mkdir(exist_ok=True);(O/'run.failed').write_text(traceback.format_exc());raise
