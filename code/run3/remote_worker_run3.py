#!/usr/bin/env python3
"""Run the frozen four configurations; archive thin means before any sampling."""
from pathlib import Path
import os,sys,time,json,hashlib,subprocess,traceback
import numpy as np
from remote_worker_run2 import vtk_map
ROOT=Path('/content/t3_run3_stage'); OUT=Path('/content/t3_run3_out')
CASES=('dx1p0_s101','dx0p5_s101','dx1p0_s102','dx0p5_s102')
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def run():
 manifest=json.loads((ROOT/'stage_manifest.json').read_text()); deadline=float(os.environ['T3_DEADLINE'])
 source=ROOT/'FluidX3D'
 with (OUT/'build.log').open('w') as f:p=subprocess.run(['make','Linux','-j8'],cwd=source,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=1500)
 if p.returncode:raise RuntimeError('build failed '+str(p.returncode))
 binary=source/'bin/FluidX3D';env={**os.environ,'LD_LIBRARY_PATH':str(source/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
 print('BUILD_OK',flush=True)
 for case in CASES:
  c=manifest['cases'][case];dx=c['dx'];base=ROOT/case;conf=base/'conf.luwpf'
  assert digest(conf)==c['conf_sha256']
  # Conservative prior-size scaling with a fixed transfer and teardown reserve.
  ref=1730*(c['cells_total']/(500*500*470))*(c['steps']/31000)
  if time.time()+2*ref+900>deadline:raise RuntimeError('budget gate before '+case)
  print('START',case,'remaining_s',round(deadline-time.time()),flush=True)
  t=time.time()
  with (OUT/f'{case}_solver.log').open('w') as f:p=subprocess.run([str(binary),str(conf)],cwd=base,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env,timeout=max(60,deadline-time.time()-600))
  (OUT/f'{case}_exit.json').write_text(json.dumps({'case':case,'solver_exit':p.returncode,'elapsed_s':time.time()-t})+'\n')
  print('SOLVER_EXIT',case,p.returncode,flush=True)
  if p.returncode:raise RuntimeError('solver failed '+case)
  files=list((base/'RESULTS/vtk').glob('*_avg-*.vtk'))
  if len(files)!=1:raise RuntimeError('VTK count '+case+' '+str(files))
  v=vtk_map(files[0]);nx,ny,nz=v['dims'];ox,oy,oz=v['origin'];d=v['spacing'][0]
  assert abs(d-dx)<1e-5 and nx==round(350/dx) and ny==round(100/dx)
  f=v['fields'];wall_k=round((0-oz)/dx)
  # Include a sub-wall layer when present to audit native boundary labels.
  kstart=max(0,wall_k);kend=min(nz,wall_k+round(25/dx)+3)
  ys=np.array([j for j in range(ny) if 40-1e-6<=oy+j*dx<=60+1e-6],dtype=int)
  assert len(ys)>=15 and kend>kstart+round(20/dx)+1
  u=np.asarray(f['u_avg'][kstart:kend,ys,:],dtype='<f4').copy()
  fluid=np.asarray(f['fluid'][kstart:kend,ys,:],dtype='<f4').copy()
  assert u.shape==(kend-kstart,len(ys),nx,3) and fluid.shape==u.shape[:3]
  meta={'case':case,'dx':dx,'vtk_sha256':digest(files[0]),'config_sha256':digest(conf),'origin':v['origin'],'spacing':v['spacing'],'dims':v['dims'],'k_start':kstart,'k_end_exclusive':kend,'y_indices':ys.tolist(),'wall_index_from_origin':wall_k,'source':'u_avg and fluid from final time-mean VTK','avg_samples_expected':500}
  dest=OUT/f'{case}_thin.npz'
  with dest.open('xb') as fp:np.savez_compressed(fp,u_avg=u,fluid=fluid,metadata=json.dumps(meta,sort_keys=True))
  sha=digest(dest);(OUT/f'{case}_thin.sha256').write_text(sha+'\n')
  (OUT/f'{case}_thin_meta.json').write_text(json.dumps(meta,indent=2)+'\n')
  print('THIN_READY',case,sha,dest.stat().st_size,flush=True)
  # Never proceed to downstream postprocessing/teardown until host verifies bytes.
  ack=OUT/f'{case}_verified.ack'
  while not ack.exists():
   if time.time()>deadline-600:raise RuntimeError('host verification missing before deadline '+case)
   time.sleep(15)
  if ack.read_text().strip()!=sha:raise RuntimeError('host acknowledgement mismatch '+case)
  print('THIN_VERIFIED_HOST',case,flush=True)
 (OUT/'run.done').write_text('complete\n');print('ALL_DONE',flush=True)
if __name__=='__main__':
 OUT.mkdir(exist_ok=False)
 try:run()
 except BaseException:
  traceback.print_exc();(OUT/'run.failed').write_text(traceback.format_exc());raise
