#!/usr/bin/env python3
"""One-shot Colab worker: compile, smoke, baseline gate, then three T4 cases.
Only producer of VM files; host must SHA-ack each thin field before proceeding.
"""
from pathlib import Path
import hashlib,json,os,subprocess,time,traceback,shutil,csv,re
import numpy as np
from t3_parser import vtk_map
ROOT=Path('/content/stage_t4');OUT=Path('/content/t4_out')
CASES=('dx1p0_s107','dx1p0_s108','dx1p0_s109')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def run(cmd,cwd,log,timeout,env=None):
 with log.open('x') as f:p=subprocess.run(cmd,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=timeout)
 return p.returncode
def extract(case,base,conf):
 files=list((base/'RESULTS/vtk').glob('*_avg-*.vtk'))
 assert len(files)==1,(case,files)
 v=vtk_map(files[0]);nx,ny,nz=v['dims'];ox,oy,oz=v['origin'];dx=v['spacing'][0]
 assert (nx,ny)==(550,100) and abs(dx-1.)<1e-5
 wall_k=round((0-oz)/dx);kstart=max(0,wall_k);kend=min(nz,wall_k+28)
 u=np.asarray(v['fields']['u_avg'][kstart:kend,:,:],dtype='<f4').copy()
 fluid=np.asarray(v['fields']['fluid'][kstart:kend,:,:],dtype='<f4').copy()
 assert u.shape==(kend-kstart,ny,nx,3) and fluid.shape==u.shape[:3]
 meta={'case':case,'dx':dx,'origin':v['origin'],'spacing':v['spacing'],'dims':v['dims'],'k_start':kstart,'k_end_exclusive':kend,'y_indices':list(range(ny)),'wall_index_from_origin':wall_k,'vtk_sha256':sha(files[0]),'config_sha256':sha(conf),'avg_samples_expected':1500,'source':'u_avg and fluid from final time-mean VTK'}
 dest=OUT/f'{case}_thin.npz'
 with dest.open('xb') as f:np.savez_compressed(f,u_avg=u,fluid=fluid,metadata=json.dumps(meta,sort_keys=True))
 digest=sha(dest);(OUT/f'{case}_thin.sha256').write_text(digest+'\n');(OUT/f'{case}_thin_meta.json').write_text(json.dumps(meta,indent=2)+'\n')
 print('THIN_READY',case,digest,dest.stat().st_size,flush=True)
 return digest
def wait_ack(case,digest,deadline):
 ack=OUT/f'{case}_verified.ack'
 while not ack.exists():
  if time.time()>deadline-900:raise RuntimeError('no verified host ACK: '+case)
  time.sleep(10)
 assert ack.read_text().strip()==digest,'host ACK hash mismatch'
 print('ACKED',case,flush=True)
def main():
 man=json.loads((ROOT/'manifest.json').read_text()); deadline=float(os.environ['T4_DEADLINE'])
 for variant in ('off','on','gate0','gate0_B'):
  src=ROOT/f'FluidX3D_{variant}'
  if variant in ('gate0','gate0_B'):
   for name,digest in man['fixture_'+('A' if variant=='gate0' else 'B')+'_sha256'].items():assert sha(src/'src'/name)==digest,(variant,name)
  elif variant=='on':
   for name,digest in man['source_sha256'].items():assert sha(src/'src'/name)==digest,(variant,name)
  rc=run(['make','Linux','-j8'],src,OUT/f'build_{variant}.log',900)
  print('BUILD',variant,rc,flush=True)
  if rc:raise RuntimeError('build failed '+variant)
 def solve(variant,case,base):
  binary=ROOT/f'FluidX3D_{variant}/bin/FluidX3D';conf=base/'conf.luwpf';env={**os.environ,'LD_LIBRARY_PATH':str(ROOT/f'FluidX3D_{variant}/src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
  t=time.time();print('START',variant,case,round(deadline-t),flush=True)
  if case=='smoke':env['LUW_GROUND_TAU_START']='0'
  elif variant=='on':env['LUW_GROUND_TAU_START']='11000'
  rc=run([str(binary),str(conf)],base,OUT/f'{case}_solver.log',max(60,deadline-t-900),env)
  (OUT/f'{case}_exit.json').write_text(json.dumps({'case':case,'exit':rc,'elapsed_s':time.time()-t})+'\n')
  results=base/'RESULTS'
  (OUT/f'{case}_results_listing.txt').write_text('\n'.join(f'{p.relative_to(results)} {p.stat().st_size}' for p in sorted(results.rglob('*')) if p.is_file())+'\n' if results.exists() else 'RESULTS ABSENT\n')
  for original,suffix in [('wall_tau_actual.csv','wall_tau_raw.csv'),('ground_eligibility.csv','ground_eligibility.csv'),('city_stability.csv','city_stability.csv')]:
   src=results/original
   if src.is_file():shutil.copyfile(src,OUT/f'{case}_{suffix}')
  gate=base/'RESULTS/t3d_geometry_gate.csv'
  if gate.exists():shutil.copyfile(gate,OUT/f'{case}_geometry_gate.csv')
  print('SOLVER_EXIT',case,rc,flush=True)
  if rc:raise RuntimeError('solver failed '+case)
  if gate.exists():
   with gate.open() as f:rows=list(csv.DictReader(f))
   assert len(rows)==5 and all(row['pass']=='1' for row in rows),'native gate failed'
  else:raise RuntimeError('native gate absent '+case)
 # On-GPU packet/address fixture before any solver case.
 fixture=run(['python3','/content/t4_gpu_link_fixture.py'],ROOT,OUT/'gpu_link_fixture.json',120)
 if fixture:raise RuntimeError('GPU linked-packet fixture failed')
 fixture_data=json.loads((OUT/'gpu_link_fixture.json').read_text())
 assert fixture_data['gpu_packet_mapping_fixture']=='PASS'
 print('GPU_LINK_FIXTURE_PASS',flush=True)
 # Run real OpenCL kernels; keep BOTH unabridged raw traces before gating.
 for variant,label in [('gate0','A'),('gate0_B','B')]:
  env={**os.environ,'LD_LIBRARY_PATH':str(ROOT/f'FluidX3D_{variant}/src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
  rc=run([str(ROOT/f'FluidX3D_{variant}/bin/FluidX3D')],ROOT,OUT/f'wall_gate0_{label}_solver.log',120,env)
  original=Path('/content/wall_gate0'+('_B' if label=='B' else '')+'.csv')
  if original.is_file():shutil.copyfile(original,OUT/f'wall_gate0_{label}.csv')
  print('WALL_GATE0_OPENCL_EXIT',label,rc,flush=True)
  if rc or not (OUT/f'wall_gate0_{label}.csv').is_file():raise RuntimeError('WALL_GATE0 '+label+' failed; raw trace preserved')
  with (OUT/f'wall_gate0_{label}.csv').open() as f:trace=list(csv.DictReader(f))
  assert len(trace)==21 and all(np.isfinite(float(v)) for row in trace for v in row.values())
  mass=[float(row['mass']) for row in trace];px=[float(row['px']) for row in trace]
  fx=[float(row['wall_fx_sum']) for row in trace]
  mass_rel=max(abs(x/mass[0]-1) for x in mass)
  residual=[px[i]-px[i-1]-fx[i]-(float(trace[i].get('bounce_counterfactual_sum',0))) for i in range(1,len(trace))]
  metrics={'mass_relative_max':mass_rel,'px0':px[0],'mass':mass,'px':px,'pz':[float(row['pz']) for row in trace], 'wall_fx':fx,'step_residual':residual,'cumulative_residual':sum(residual),'threshold_mass':1e-6,'threshold_px':1e-4*abs(px[0])}
  (OUT/f'wall_gate0_{label}_metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
  print('WALL_GATE0_METRICS',label,'MASS_REL',mass_rel,'MAX_STEP_RESIDUAL',max(map(abs,residual)),'CUM_RESIDUAL',sum(residual),flush=True)
  if label=='A':a_gate_pass=mass_rel<=1e-6 and abs(sum(residual))<=1e-4*abs(px[0])
  if label=='B':print('WALL_GATE0_B_DIAGNOSTIC',max(map(abs,residual)),sum(residual),flush=True)
 if not a_gate_pass:raise RuntimeError('WALL_GATE0 A conservation gate failed; A/B raw traces preserved')
 # Smoke uses small spatial lattice but >11000 steps to trigger actual wall-stress output.
 assert sha(ROOT/'smoke/conf.luwpf')==man['smoke_conf_sha256']
 solve('on','smoke',ROOT/'smoke')
 tau=ROOT/'smoke/RESULTS/wall_tau_actual.csv'
 assert tau.exists() and tau.stat().st_size>100,'wall tau output absent'
 shutil.copyfile(tau,OUT/'smoke_wall_tau.csv')
 with tau.open() as f:rows=list(csv.DictReader(f))
 valid=[r for r in rows if float(r['count'])>0 and np.isfinite(float(r['ustar_mps']))]
 assert valid and max(float(r['ustar_mps']) for r in valid)>0,'no wall stress'
 print('SMOKE_TAU',len(valid),valid[len(valid)//2],flush=True)
 # Host must inspect smoke evidence before authorizing expensive full-size solves.
 (OUT/'smoke_ready').write_text('ok\n')
 while not (OUT/'smoke_verified.ack').exists():
  if time.time()>deadline-900:raise RuntimeError('smoke ACK not received')
  time.sleep(10)
 assert (OUT/'smoke_verified.ack').read_text().strip()=='ok'
 # Stage A: changed source macro OFF, physical 1-m seed 107.
 baseline=ROOT/'dx1p0_s107';assert sha(baseline/'conf.luwpf')==man['cases']['dx1p0_s107']['conf_sha256']
 solve('off','off_s107',baseline); digest=extract('off_s107',baseline,baseline/'conf.luwpf');wait_ack('off_s107',digest,deadline)
 # Host compares native arrays bytewise with archived T3d before granting B.
 while not (OUT/'baseline_gate.ack').exists():
  if time.time()>deadline-900:raise RuntimeError('baseline gate missing')
  time.sleep(10)
 assert (OUT/'baseline_gate.ack').read_text().strip()=='PASS'
 # Do not reuse a case root: clone config/inputs into fresh exclusive paths.
 for seed in (107,108,109):
  case=f'wm_s{seed}';source=ROOT/f'dx1p0_s{seed}';base=ROOT/case
  assert not base.exists();shutil.copytree(source,base)
  assert sha(base/'conf.luwpf')==man['cases'][f'dx1p0_s{seed}']['conf_sha256']
  if time.time()+1500>deadline:raise RuntimeError('budget gate before '+case)
  solve('on',case,base);digest=extract(case,base,base/'conf.luwpf');wait_ack(case,digest,deadline)
  tau=base/'RESULTS/wall_tau_actual.csv'
  if tau.exists():shutil.copyfile(tau,OUT/f'{case}_wall_tau.csv')
 (OUT/'run.done').write_text('complete\n');print('ALL_DONE',flush=True)
if __name__=='__main__':
 OUT.mkdir(exist_ok=False)
 try:main()
 except BaseException:
  (OUT/'run.failed').write_text(traceback.format_exc());traceback.print_exc();raise
