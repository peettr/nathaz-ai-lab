#!/usr/bin/env python3
"""T11 two-seed T5-off worker; only solver executable may be stubbed in local test."""
import argparse,hashlib,json,math,os,pathlib,shutil,subprocess,tarfile,time,traceback
import numpy as np
from remote_worker_run2 import vtk_map
from t5_sampling import write_points

CASES=('E_s101_off','E_s102_off')
PRODUCTS=('points80.json','upstream_slice.npz','profile.json','solver.log','actual_opencl.cl','exit.json')
BASE_SETUP='ce1a1a71bc34be8933d8494a3e7512481a0f3a958c08cb79c20fc31c1e5eeb90'
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
def profile(v,obs,case,src,conf,vtk,out):
 f=v['fields'];assert 'tke' in f
 sl=np.s_[20:82,150:351,0:61]
 meta={'k_start':20,'k_end_exclusive':82,'x_start':0,'x_end_exclusive':61,'y_start':150,'y_end_exclusive':351,'dims':v['dims'],'origin':v['origin'],'spacing':v['spacing'],'numerical_wall_z_m':0.5,'vtk_sha256':sha(vtk),'config_sha256':sha(conf),'source_setup_sha256':sha(src/'src/setup.cpp'),'averaging_steps':[20000,31000,40]}
 with (out/(case+'_upstream_slice.npz')).open('xb') as q:np.savez_compressed(q,u_avg=np.asarray(f['u_avg'][sl],dtype='<f4'),speed_mean=np.asarray(f['speed_mean'][sl],dtype='<f4'),tke=np.asarray(f['tke'][sl],dtype='<f4'),fluid=np.asarray(f['fluid'][sl],dtype='u1'),metadata=json.dumps(meta))
 rows=[]
 for x in (5,30,45):
  for row in obs['rows']:
   z=float(row['z_m']);k=math.floor(z+20.5);w=z+20.5-k;jj=np.arange(150,351)
   assert 20<=k and k+1<82
   good=(f['fluid'][k,jj,x]>.5)&(f['fluid'][k+1,jj,x]>.5)
   assert good.sum()>0
   km=float(((1-w)*np.asarray(f['tke'][k,jj,x],dtype='f8')+w*np.asarray(f['tke'][k+1,jj,x],dtype='f8'))[good].mean())
   um=float(((1-w)*np.asarray(f['u_avg'][k,jj,x,0],dtype='f8')+w*np.asarray(f['u_avg'][k+1,jj,x,0],dtype='f8'))[good].mean())
   ko=float(row['k_obs_m2s2']);uo=float(row['U_obs_mps'])
   rows.append(dict(x_m=x,height_agl_m=z,fluid_columns=int(good.sum()),total_columns=len(jj),k_model_m2s2=km,k_obs_m2s2=ko,kappa=km/ko,U_model_streamwise_mps=um,U_obs_mps=uo,U_ratio=um/uo))
 (out/(case+'_profile.json')).write_text(json.dumps(dict(source_observation_sha256=obs['source_sha256'],profile=rows,window='steps 20000..31000 stride40',method='T8: z-linear interpolation of tke and streamwise ux, arithmetic mean across supported y=150..350'),indent=2)+'\n')
def main(c,stub):
 b=json.loads((c/'t11_budget.json').read_text());mode=b['mode'];deadline=b['work_deadline'];o=c/'t11/out';o.mkdir(parents=True)
 try:
  if stub and (c==pathlib.Path('/content') or mode!='fixture'):raise ValueError('stub only in isolated fixture')
  if not stub and mode!='production':raise ValueError('production budget required')
  arc=c/'stage_t5.tar.gz';assert sha(arc)==json.loads((c/'archive.json').read_text())['sha256']
  root=c/'t11';unpack(arc,root);stage=root/'stage';man=json.loads((stage/'manifest.json').read_text());src=stage/'FluidX3D_off';setup=src/'src/setup.cpp'
  assert sha(setup)==BASE_SETUP
  patch=c/'setup_t11.cpp';assert sha(patch)==json.loads((c/'setup_manifest.json').read_text())['sha256']
  shutil.copyfile(patch,setup)
  ref=json.loads((c/'B2u_reference_points.json').read_text());assert len(ref['rows'])==80 and ref['uref']==3.9286416
  obs=json.loads((c/'comparison.json').read_text());assert len(obs['rows'])==6
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
   if rc:raise RuntimeError('solver exit '+str(rc))
   if not cl.is_file() or not cl.stat().st_size:raise RuntimeError('missing actual OpenCL')
   seal(cl)
   vtk=list((dest/'RESULTS/vtk').glob('*_avg-*.vtk'));assert len(vtk)==1,vtk
   v=vtk_map(vtk[0]);expected=(500,500,82) if stub else (500,500,270);origin=(0.,0.,-20.)
   assert v['dims']==expected and v['origin']==origin and v['spacing']==(1.,1.,1.),(v['dims'],v['origin'])
   points=write_points(o,case,ref,v,vtk,sha);seal(points)
   profile(v,obs,case,src,cfg,vtk[0],o)
   for suffix in ('upstream_slice.npz','profile.json'):seal(o/(case+'_'+suffix))
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
