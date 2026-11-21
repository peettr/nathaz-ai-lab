#!/usr/bin/env python3
"""GPU-only A then B, each thin field host-verified before continuing."""
import pathlib,json,hashlib,tarfile,subprocess,os,time,traceback,shutil,csv
import numpy as np
from remote_worker_run2 import vtk_map
R=pathlib.Path('/content'); S=R/'stage'; O=R/'phaseab_out'; CASES=[('A','dx1p0_s107','FluidX3D_off')]+[('B',f'dx1p0_s{s}','FluidX3D_on') for s in (107,108,109)]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def run():
 O.mkdir(exist_ok=False)
 archive=R/'stage_phase.tar.gz';assert sha(archive)==json.loads((R/'archive.json').read_text())['sha256']
 with tarfile.open(archive) as t:
  for m in t.getmembers():assert m.name=='stage' or m.name.startswith('stage/');assert '..' not in pathlib.PurePath(m.name).parts and (m.isfile() or m.isdir())
  assert not S.exists();t.extractall(R,filter='data')
 man=json.loads((S/'phase_manifest.json').read_text());deadline=float(os.environ['PHASE_DEADLINE'])
 for stage,case,tree in CASES:
  src=S/tree
  for n,h in man['source_on' if stage=='B' else 'source_off'].items():assert sha(src/'src'/n)==h,(tree,n)
  build=O/f'{stage}_build.log'
  with build.open('x') as f:p=subprocess.run(['make','Linux','-j8'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=1200)
  print('BUILD',stage,p.returncode,flush=True)
  if p.returncode:raise RuntimeError(f'{stage} build failed')
  for phase,seed_case,which in [x for x in CASES if x[0]==stage]:
   label=f'{phase}_{seed_case}';required=700 if phase=='A' else 750
   base=R/'phaseab_cases'/label
   assert not base.exists()
   shutil.copytree(S/seed_case,base,symlinks=True)
   conf=base/'conf.luwpf';assert sha(conf)==man['cases'][seed_case]['conf_sha256']
   if time.time()+required+300>deadline:raise RuntimeError('CU deadline before '+label)
   env={**os.environ,'LD_LIBRARY_PATH':str(src/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH',''),'LUW_GROUND_MIX_A':'0'}
   if phase=='B':env['LUW_CAPTURE_CL']=str(O/f'{label}_actual_opencl.cl')
   print('START',label,'remaining',round(deadline-time.time()),flush=True)
   t=time.time()
   with (O/f'{label}_solver.log').open('x') as f:p=subprocess.run([str(src/'bin/FluidX3D'),str(conf)],cwd=base,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=min(1800,max(60,deadline-time.time()-250)))
   (O/f'{label}_exit.json').write_text(json.dumps({'solver_exit':p.returncode,'elapsed_s':time.time()-t})+'\n')
   print('SOLVER_EXIT',label,p.returncode,flush=True)
   if p.returncode:raise RuntimeError('solver failed '+label)
   gates=list((base/'RESULTS').glob('t3d_geometry_gate.csv'));assert len(gates)==1
   shutil.copyfile(gates[0],O/f'{label}_geometry_gate.csv')
   with gates[0].open() as f:rows=list(csv.DictReader(f))
   assert len(rows)==5 and all(r['pass']=='1' for r in rows),'geometry gate '+label
   vtk=list((base/'RESULTS/vtk').glob('*_avg-*.vtk'));assert len(vtk)==1,(label,vtk)
   v=vtk_map(vtk[0]);nx,ny,nz=v['dims'];dx=v['spacing'][0];ox,oy,oz=v['origin']
   assert abs(dx-1.)<1e-5 and nx==550 and ny==100
   kstart=round((0-oz)/dx);kend=kstart+28
   u=np.asarray(v['fields']['u_avg'][kstart:kend,:,:],dtype='<f4').copy();fluid=np.asarray(v['fields']['fluid'][kstart:kend,:,:],dtype='<f4').copy()
   assert u.shape==(28,100,550,3) and fluid.shape==(28,100,550)
   metadata={'case':seed_case,'dx':dx,'origin':v['origin'],'spacing':v['spacing'],'dims':v['dims'],'k_start':kstart,'k_end_exclusive':kend,'y_indices':list(range(ny)),'wall_index_from_origin':kstart,'config_sha256':sha(conf),'vtk_sha256':sha(vtk[0]),'source':'u_avg and fluid from final time-mean VTK','avg_samples_expected':1500}
   with (O/f'{label}_thin.npz').open('xb') as f:np.savez_compressed(f,u_avg=u,fluid=fluid,metadata=json.dumps(metadata,sort_keys=True))
   digest=sha(O/f'{label}_thin.npz');(O/f'{label}_thin.sha256').write_text(digest+'\n');(O/f'{label}_thin_meta.json').write_text(json.dumps(metadata,indent=2)+'\n')
   if phase=='B':
    for name in ('ground_excluded.csv','ground_eligibility.csv','wall_tau_actual.csv','city_stability.csv'):
     p=base/'RESULTS'/name
     if p.is_file():shutil.copyfile(p,O/f'{label}_{name}')
    cl=O/f'{label}_actual_opencl.cl';assert cl.is_file() and 'ground_initialize_incoming' in cl.read_text()
   print('THIN_READY',label,digest,flush=True)
   ack=O/f'{label}.ack'
   while not ack.exists():
    if time.time()+240>deadline:raise RuntimeError('ack timeout '+label)
    time.sleep(10)
   if ack.read_text().strip()!=digest:raise RuntimeError('ack mismatch '+label)
   if phase=='A':
    verdict=O/'A_verdict.json'
    while not verdict.is_file():
     if time.time()+240>deadline:raise RuntimeError('phase A gate timeout')
     time.sleep(10)
    if not json.loads(verdict.read_text())['bitwise_equal']:
     (O/'run.stopped_A').write_text('phase A mismatch\n');print('STOP_A_MISMATCH',flush=True);return
   print('HOST_VERIFIED',label,flush=True)
 (O/'run.done').write_text('complete\n');print('ALL_DONE',flush=True)
if __name__=='__main__':
 try:run()
 except BaseException:
  traceback.print_exc();O.mkdir(exist_ok=True);(O/'run.failed').write_text(traceback.format_exc());raise
