#!/usr/bin/env python3
"""T13 two-seed T5-off worker; only solver executable may be stubbed in local test."""
import argparse,hashlib,json,math,os,pathlib,shutil,subprocess,tarfile,time,traceback
import numpy as np
from remote_worker_run2 import vtk_map
from t5_sampling import write_points

CASES=('E_s101_off','E_s102_off')
PRODUCTS=('points80.json','solver.log','actual_opencl.cl','exit.json','city_stability.csv')
BASE_KERNEL='11f06a62aef7200af972a5420c52ee37c8f404c4d41fca6a8d4bada0d6dfe555'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def seal(p):
 h=sha(p);(p.parent/(p.name+'.sha256')).write_text(h+'\n');print('READY',p.name,h,flush=True);return h
def unpack(p,d):
 with tarfile.open(p) as t:
  for m in t:
   if not (m.name=='stage' or m.name.startswith('stage/')) or '..' in pathlib.PurePosixPath(m.name).parts or not (m.isfile() or m.isdir()):raise ValueError('unsafe member '+m.name)
  t.extractall(d,filter='data')
def main(c,stub):
 b=json.loads((c/'t13b_budget.json').read_text());mode=b['mode'];deadline=b['work_deadline'];o=c/'t13b/out';o.mkdir(parents=True)
 try:
  if stub and (c==pathlib.Path('/content') or mode!='fixture'):raise ValueError('stub only in isolated fixture')
  if not stub and mode!='production':raise ValueError('production budget required')
  arc=c/'stage_t5.tar.gz';assert sha(arc)==json.loads((c/'archive.json').read_text())['sha256']
  root=c/'t13b';unpack(arc,root);stage=root/'stage';man=json.loads((stage/'manifest.json').read_text());src=stage/'FluidX3D_off';kernel=src/'src/kernel.cpp'
  assert sha(kernel)==BASE_KERNEL
  patch=c/'kernel_t13b.cpp';assert sha(patch)==json.loads((c/'kernel_manifest.json').read_text())['sha256']
  shutil.copyfile(patch,kernel)
  defines=src/'src/defines.hpp'; d=defines.read_text(); assert 'SMAG_CS_013' not in d
  defines.write_text(d+'\n#define SMAG_CS_013\n')
  ref=json.loads((c/'B2u_reference_points.json').read_text());assert len(ref['rows'])==80 and ref['uref']==3.9286416
  if time.time()+(0 if stub else 2200)>=deadline:raise TimeoutError('insufficient budget before build')
  with (o/'build.log').open('x') as log:rc=subprocess.run(['make','Linux','-j8'],cwd=src,stdout=log,stderr=subprocess.STDOUT,timeout=900).returncode
  seal(o/'build.log');assert rc==0
  exe=src/'bin/FluidX3D';assert exe.is_file() and os.access(exe,os.X_OK)
  if stub:shutil.copyfile(stub,exe);print('FIXTURE_ONLY solver binary replaced',flush=True)
  for case in CASES:
   if time.time()+(0 if stub else 2250)>=deadline:raise TimeoutError('insufficient budget before '+case)
   original=stage/'cases'/case;conf=original/'conf.luwpf';assert sha(conf)==man['cases'][case]['config_sha256']
   text=conf.read_text();seed=int(case.split('_')[1][1:]);assert all(text.splitlines().count(x)==1 for x in ('run_nstep = 31000','purge_avg = 20000','purge_avg_stride = 40',f'vk_inlet_seed = {seed}'))
   dest=root/('case_'+case);shutil.copytree(original,dest);cfg=dest/'conf.luwpf'
   cl=o/(case+'_actual_opencl.cl');env={**os.environ,'LUW_CAPTURE_CL':str(cl),'LUW_GROUND_MIX_A':'0','LD_LIBRARY_PATH':str(src/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
   print('SOLVE',case,'remaining',round(deadline-time.time()),flush=True)
   start=time.time();rc=None
   try:
    with (o/(case+'_solver.log')).open('x') as log:rc=subprocess.run([str(exe),str(cfg)],cwd=dest,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=max(1,min(4500,deadline-time.time()-220))).returncode
   finally:
    seal(o/(case+'_solver.log'))
    (o/(case+'_exit.json')).write_text(json.dumps(dict(solver_exit=rc,elapsed_s=time.time()-start))+'\n');seal(o/(case+'_exit.json'))
   # Preserve native time-resolved stability extrema even on a nonzero solver exit.
   monitor=dest/'RESULTS/city_stability.csv'
   if monitor.is_file() and monitor.stat().st_size:
    shutil.copyfile(monitor,o/(case+'_city_stability.csv'));seal(o/(case+'_city_stability.csv'))
   if rc:raise RuntimeError('solver exit '+str(rc))
   monitor=dest/'RESULTS/city_stability.csv'
   if stub:
    monitor.parent.mkdir(exist_ok=True,parents=True)
    monitor.write_text('step,max_u_lattice,first_nonfinite_xyz_component\n50,0.1,\n')
   if not monitor.is_file() or not monitor.stat().st_size:raise RuntimeError('missing city stability trace')
   if not (o/(case+'_city_stability.csv')).exists():shutil.copyfile(monitor,o/(case+'_city_stability.csv'));seal(o/(case+'_city_stability.csv'))
   if not cl.is_file() or not cl.stat().st_size:raise RuntimeError('missing actual OpenCL')
   seal(cl)
   vtk=list((dest/'RESULTS/vtk').glob('*_avg-*.vtk'));assert len(vtk)==1,vtk
   v=vtk_map(vtk[0]);expected=(500,500,82) if stub else (500,500,270);origin=(0.,0.,-20.)
   assert v['dims']==expected and v['origin']==origin and v['spacing']==(1.,1.,1.),(v['dims'],v['origin'])
   points=write_points(o,case,ref,v,vtk,sha);seal(points)
   names=[case+'_'+n for n in PRODUCTS]+(['build.log'] if case==CASES[0] else [])
   hashes={n:(o/(n+'.sha256')).read_text().strip() for n in names}
   hand=o/(case+'_handoff.json');hand.write_text(json.dumps(dict(sha256=hashes,mode=mode))+'\n');seal(hand)
   ack=o/(case+'.ack.json')
   while not ack.exists():
    if time.time()+2>=deadline:raise TimeoutError('ACK deadline')
    time.sleep(.2 if stub else 2)
   if json.loads(ack.read_text())!=hashes:raise RuntimeError('ACK mismatch')
   print('HOST_VERIFIED',case,flush=True)
  done=o/'run.done';done.write_text(json.dumps(dict(verified_cases=list(CASES),mode=mode))+'\n');seal(done)
 except BaseException:
  p=o/'run.failed';p.write_text(traceback.format_exc());seal(p);raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--content',type=pathlib.Path,default=pathlib.Path('/content'));p.add_argument('--stub',type=pathlib.Path);a=p.parse_args();main(a.content.resolve(),a.stub.resolve() if a.stub else None)
