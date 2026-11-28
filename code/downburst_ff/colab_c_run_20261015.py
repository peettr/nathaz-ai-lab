"""A3-C Colab-only storm threshold counterfactual and stationary-wind false-stop probe.
Inputs: a3_b_colab_bundle_1014.tar.gz and OpenFAST 5 binary; no local solver.
Every threshold is frozen from generated wind before structural output is read.
"""
import os,sys,json,time,gzip,tarfile,shutil,subprocess,concurrent.futures,traceback
from pathlib import Path
import numpy as np
P=Path('/content/a3_c_1015')
GROUPS={'G1L_22':22.,'G1L_20':20.,'G1L_18':18.}

def setup():
 P.mkdir(exist_ok=False)
 with tarfile.open('/content/a3_b_colab_bundle_1014.tar.gz') as f:f.extractall(P,filter='data')
 (P/'bin').mkdir()
 with gzip.open('/content/openfast_5_linux_1014.gz','rb') as f,(P/'bin/openfast').open('wb') as w:shutil.copyfileobj(f,w)
 (P/'bin/openfast').chmod(0o755)
 print('openfast',subprocess.run([str(P/'bin/openfast'),'-v'],capture_output=True,text=True).stdout[-400:],os.cpu_count(),flush=True)
 (P/'runs').mkdir();(P/'results').mkdir()
 (P/'.colab_owner').write_text('A3-C researchos-lab-ideas phase C 20261015')

def modules():
 sys.path.insert(0,str(P/'code'))
 import segment_b_run as b,segment_a_run as a
 from wind_field_probe import CASES
 from analyze_segment_b import read_out,measures
 b.BASE=P/'base';b.ROOT=P/'runs';b.SRC=P/'base/ff_smoke_feedback';b.FAST=P/'bin/openfast';b.LIB=P/'base/rosco210_ff_build_guo_v2/libdiscon.so';a.CURVE=P/'base/segment_a_v4_curve.txt'
 return b,a,CASES,read_out,measures

def prepare():
 b,a,CASES,_,_=modules()
 manifest=[]
 for case in CASES:
  for seed in b.SEEDS:
   root=P/'runs'/f'{case.name}_s{seed}';root.mkdir(exist_ok=False)
   p=b.make_seed(case,seed,root)
   b.phase_correct_bts(root/'wind.bts',root/'corrected.bts')
   (root/'wind.bts').rename(root/'wind_unshifted.bts');(root/'corrected.bts').rename(root/'wind.bts')
   p['bts_phase_correction']='14 x 0.5 s initial frames inserted; measured OpenFAST +7s lookup'
   data=np.load(root/'signals.npz');t=data['t']+p['start_abs_s'];v=data['rotor_3s']
   for group,threshold in GROUPS.items():
    hit=b.first_cross(t[t<=p['end_abs_s']],v[t<=p['end_abs_s']],threshold)
    assert hit is not None,(case.name,seed,group)
    p['trigger_abs_s'][group]=hit
    manifest.append(dict(case=case.name,seed=seed,group=group,threshold_mps=threshold,trigger_abs_s=hit,actual_lead_s=p['rotor_3s_first25_abs_s']-hit,start_abs_s=p['start_abs_s'],end_abs_s=p['end_abs_s'],source=str(root)))
   (root/'provenance.json').write_text(json.dumps(p,indent=2))
   print('GENERATED',case.name,seed,[round(p['trigger_abs_s'][g],1) for g in GROUPS],flush=True)
 (P/'results/manifest.json').write_text(json.dumps(manifest,indent=2))
 print('PREPARED',len(manifest),flush=True)

def one(row):
 b,a,_,read_out,measures=modules();key=f"{row['case']}_s{row['seed']}_{row['group']}";f=P/'results'/(key+'.json')
 if f.exists():return key,json.loads(f.read_text())['returncode']
 dest=b.stage(row);p=json.loads((Path(row['source'])/'provenance.json').read_text())
 a.replace_key(dest/'NREL-5MW.fst','OutFileFmt','1')
 a.replace_key(dest/'NREL-5MW.fst','TStart',f"{max(0.,p['rotor_3s_first13_abs_s']-row['start_abs_s']-5):.3f}")
 env=os.environ.copy();env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(a.CURVE),ROSCO_FF_GAIN_DEG_PER_MS='0',OMP_NUM_THREADS='1')
 start=time.monotonic()
 with (dest/'openfast.log').open('w') as log:
  try:rc=subprocess.run([str(b.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900).returncode
  except subprocess.TimeoutExpired:rc=-999
 entry=dict(row,returncode=rc,wall_s=round(time.monotonic()-start,3))
 if rc==0:
  d=read_out(dest/'NREL-5MW.out');assert abs(d['Time'][-1]-(row['end_abs_s']-row['start_abs_s']))<.051
  entry['metrics']=measures(d,p,row['start_abs_s']);entry['event_window_abs_s']=[p['rotor_3s_first13_abs_s'],p['rotor_3s_last25_abs_s']+60]
 else:entry['log_tail']=(dest/'openfast.log').read_text(errors='replace')[-2500:]
 f.write_text(json.dumps(entry,indent=2));print('DONE',key,rc,entry['wall_s'],flush=True)
 return key,rc

def storm():
 manifest=json.loads((P/'results/manifest.json').read_text());assert len(manifest)==36
 with concurrent.futures.ThreadPoolExecutor(max_workers=min(6,max(1,os.cpu_count()//2))) as pool:
  futs=[pool.submit(one,r) for r in manifest]
  for f in concurrent.futures.as_completed(futs):
   try:print('PROGRESS',f.result(),flush=True)
   except BaseException:print('ERROR',traceback.format_exc(),flush=True)
 rows=[json.loads(f.read_text()) for f in sorted((P/'results').glob('G1L*.json'))]
 # files start with path/seed, not group: use manifest keys instead
 rows=[]
 for r in manifest:
  f=P/'results'/(f"{r['case']}_s{r['seed']}_{r['group']}.json")
  if f.exists():rows.append(json.loads(f.read_text()))
 (P/'results/storm_completion.json').write_text(json.dumps(dict(expected=36,success=sum(r['returncode']==0 for r in rows),fail=[(r['case'],r['seed'],r['group']) for r in rows if r['returncode']!=0],missing=len(manifest)-len(rows)),indent=2))
 print('STORM_COMPLETE',len(rows),sum(r['returncode']==0 for r in rows),flush=True)

def stationary():
 b,a,_,_,_=modules()
 # IEC 61400-1 Ed3 category B longitudinal NTM target sigma1=Iref(0.75 U+5.6), Iref=0.14.
 # Kaimal-shaped spectra and B longitudinal coherence approximation via existing B code; not TurbSim-certified IEC realization.
 # Same 7x7 rotor + upstream 1D 3x3 grid/coherence and processing as segment B.
 seeds=b.SEEDS; rotor=[(0.,float(y),float(z)) for y in b.Y for z in b.Z]
 preview=[(-float(b.D),float(y),float(z)) for y in (-42.,0.,42.) for z in (48.,90.,132.)]
 coords=rotor+preview;disk=np.array([y*y+(z-90)**2<=63**2 for _,y,z in rotor]);dt=b.DT
 rows=[]
 for mean in (18.,20.,22.):
  for seed in seeds:
   key=f'stationary_U{int(mean)}_s{seed}';f=P/'results'/(key+'.json')
   if f.exists():rows.append(json.loads(f.read_text()));continue
   t=np.arange(0,600.+dt/2,dt);k=b.spectral_field(seed+10000+int(mean)*100,len(t),coords)
   sigma=.14*(.75*mean+5.6)
   # longitudinal sigma IEC B; v/w amplitudes are assumed ratios, z^0.2 mean profile.
   U=np.array([mean*(z/90.)**.2 for x,y,z in coords],float)
   u=U[:,None]+sigma*k[0];v=.8*sigma*k[1]
   rotor_u=u[:49][disk].mean(axis=0);rotor_v=v[:49][disk].mean(axis=0)
   rotor=b.moving3(t,np.hypot(rotor_u,rotor_v))
   up_raw=np.hypot(u[49:].mean(axis=0),v[49:].mean(axis=0))
   up_filt=a.smooth(up_raw,dt,1.);up_lag=np.interp(t-1.,t,up_filt,left=up_filt[0]);up=b.moving3(t,up_lag)
   signal={'G1_25':rotor,'G1L_22':rotor,'G1L_20':rotor,'G1L_18':rotor,'G2_1D_25':up}
   limit={'G1_25':25.,'G1L_22':22.,'G1L_20':20.,'G1L_18':18.,'G2_1D_25':25.}
   def starts(arr,thr):
    hit=np.isfinite(arr)&(arr>thr);return t[np.flatnonzero(hit&~np.r_[False,hit[:-1]])].tolist()
   entry=dict(mean_mps=mean,seed=seed,sigma1_target_mps=sigma,
       rotor_3s_max_mps=float(np.nanmax(rotor)),upstream_3s_max_mps=float(np.nanmax(up)),
       rules={g:dict(episodes=starts(x,limit[g]),false_stop=bool(len(starts(x,limit[g])))) for g,x in signal.items()},
       method='600s stationary IEC Ed3-B NTM sigma, Kaimal-shaped normalized spectrum, B synthetic exponential x/y/z coherence and B 3x3 upstream 1s filter+1s delay; approximate IEC not official TurbSim')
   f.write_text(json.dumps(entry));rows.append(entry)
   print('STATIONARY',key,{g:int(z['false_stop']) for g,z in entry['rules'].items()},flush=True)
 (P/'results/stationary_completion.json').write_text(json.dumps(dict(expected=18,completed=len(rows),false_stops={g:sum(r['rules'][g]['false_stop'] for r in rows) for g in rows[0]['rules']}),indent=2))
 print('STATIONARY_COMPLETE',len(rows),flush=True)

if __name__=='__main__':{'setup':setup,'prepare':prepare,'storm':storm,'stationary':stationary}[sys.argv[1]]()
