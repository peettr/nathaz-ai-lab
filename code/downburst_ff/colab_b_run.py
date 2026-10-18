"""A3 B Colab-only continuation. No local OpenFAST and no old result modification."""
import os,sys,json,time,math,subprocess,concurrent.futures,traceback
from pathlib import Path
import numpy as np
P=Path('/content/a3_b_1014');sys.path.insert(0,str(P/'code'))
import segment_b_run as b,segment_a_run as a
from wind_field_probe import CASES,D
from analyze_segment_b import read_out,measures
b.BASE=P/'base';b.ROOT=P/'runs';b.SRC=P/'base/ff_smoke_feedback';b.FAST=P/'bin/openfast';b.LIB=P/'base/rosco210_ff_build_guo_v2/libdiscon.so';a.CURVE=P/'base/segment_a_v4_curve.txt'
GROUPS=b.GROUPS+['G5_ff_1D','G6_ff_2D','G7_ideal_2Dlead','G8_ideal_1Dlead']
SEEDS=b.SEEDS
SAVED=P/'results';SAVED.mkdir(exist_ok=True)

def prepare():
 for case in CASES:
  for seed in SEEDS:
   target=b.ROOT/f'{case.name}_s{seed}'
   if target.exists():
    p=json.loads((target/'provenance.json').read_text());print('reuse regenerated seed',case.name,seed,flush=True)
   else:
    target.mkdir()
    p=b.make_seed(case,seed,target)
    b.phase_correct_bts(target/'wind.bts',target/'wind_corrected.bts')
    (target/'wind.bts').rename(target/'wind_unshifted.bts');(target/'wind_corrected.bts').rename(target/'wind.bts')
    p['bts_phase_correction']='14 x 0.5 s initial frames inserted: v3 pilot exact hub t+7 s OpenFAST offset; all triggering histories unchanged'
    (target/'provenance.json').write_text(json.dumps(p,indent=2))
    print('generated',case.name,seed,p['rotor_3s_first25_abs_s'],flush=True)
  
 manifest=[]
 for case in CASES:
  for seed in SEEDS:
   target=b.ROOT/f'{case.name}_s{seed}'
   p=json.loads((target/'provenance.json').read_text())
   for group in GROUPS:
    when=p['trigger_abs_s'].get(group,p['trigger_abs_s']['G0_50s'])
    manifest.append(dict(case=case.name,seed=seed,group=group,trigger_abs_s=when,actual_lead_s=p['rotor_3s_first25_abs_s']-when if when is not None else None,start_abs_s=p['start_abs_s'],end_abs_s=p['end_abs_s'],source=str(target)))
 target=SAVED/'manifest.json';assert not target.exists();target.write_text(json.dumps(manifest,indent=2));print('MANIFEST',len(manifest),flush=True)

def exp_filter(x,fc=.10):
 y=np.empty_like(x,dtype=float);y[0]=x[0];alpha=1-math.exp(-2*math.pi*fc*b.DT)
 for i in range(1,len(x)):y[i]=y[i-1]+alpha*(x[i]-y[i-1])
 return y

def preview(row):
 source=Path(row['source']);data=np.load(source/'signals.npz')
 t=data['t'];n=1 if row['group'] in ('G5_ff_1D','G8_ideal_1Dlead') else 2
 raw=data[f'preview{n}'];rotor=data['rotor_speed'];lead=n*D/np.maximum(raw,1.)
 tf=1/(2*math.pi*.10);buffer=np.maximum(0.,lead-tf-.22-.5)
 if row['group'] in ('G7_ideal_2Dlead','G8_ideal_1Dlead'):
  # Perfect rotor future with exactly the same measured upstream lead trajectory.
  ideal_future=np.interp(t+lead,t,rotor,right=rotor[-1])
  filtered=exp_filter(ideal_future)
 else:filtered=exp_filter(raw)
 signal=np.interp(t-buffer,t,filtered,left=filtered[0])
 return t,signal,dict(lead_min=float(lead.min()),lead_max=float(lead.max()),buffer_min=float(buffer.min()),buffer_max=float(buffer.max()),fc_Hz=.10,filter_s=tf,pitch_s=.22,window_s=1.,input_definition='rotor(t+Tlead) filtered then buffered' if 'ideal' in row['group'] else 'upstream filtered then buffered',signal_min=float(signal.min()),signal_max=float(signal.max()))

def do_one(row):
 key=f"{row['case']}_s{row['seed']}_{row['group']}";metricfile=SAVED/(key+'.json')
 if metricfile.exists():return key,'exists',0.
 if row['trigger_abs_s'] is None:
  metricfile.write_text(json.dumps(dict(row,returncode=-2,reason='no upstream detection')));return key,'missing_detection',0.
 dest=b.stage(row)
 if row['group'].startswith(('G5_','G6_','G7_','G8_')):
  t,u,info=preview(row)
  with (dest/'preview.txt').open('w') as f:
   f.write('# t(s) u_preview(m/s); A3-B Guo-inspired fc=0.10 Hz\n')
   for tt,v in zip(t,u):f.write(f'{tt:.3f} {v:.6f}\n')
  gain='1'
 else:gain='0';info={}
 # Keep just text channels and 5s before event; solver still starts from t=0.
 p=json.loads((Path(row['source'])/'provenance.json').read_text())
 a.replace_key(dest/'NREL-5MW.fst','OutFileFmt','1')
 a.replace_key(dest/'NREL-5MW.fst','TStart',f"{max(0.,p['rotor_3s_first13_abs_s']-row['start_abs_s']-5):.3f}")
 env=os.environ.copy();env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(a.CURVE),ROSCO_FF_GAIN_DEG_PER_MS=gain)
 t0=time.monotonic()
 with (dest/'openfast.log').open('w') as log:
  try:rc=subprocess.run([str(b.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=650).returncode
  except subprocess.TimeoutExpired:rc=-999
 wall=time.monotonic()-t0
 entry=dict(row,runroot=str(dest),returncode=rc,wall_s=round(wall,3),ff=info)
 if rc==0:
  d=read_out(dest/'NREL-5MW.out');entry['metrics']=measures(d,p,row['start_abs_s']);entry['last_sim_s']=float(d['Time'][-1]);entry['first_output_s']=float(d['Time'][0]);entry['versions']='OpenFAST 5.0.0, ROSCO 2.10.6 patched Apache-2.0'
  if row['seed']==112 and row['group'] in ('G1_instant','G2_real_1D','G5_ff_1D','G6_ff_2D','G7_ideal_2Dlead'):
   np.savez_compressed(SAVED/(key+'.npz'),**{k:d[k][::10] for k in d})
 else:entry['log_tail']=(dest/'openfast.log').read_text(errors='replace')[-2000:]
 metricfile.write_text(json.dumps(entry,indent=2))
 print('DONE',key,rc,round(wall,1),flush=True)
 return key,rc,wall

def run_batch(start,stop):
 manifest=json.loads((SAVED/'manifest.json').read_text())
 existing=set()
 # Existing 26 stay on 工作站, not re-solved. Validation pilot is one already existing run.
 prior=json.loads((P/'prior_26.json').read_text())
 for r in prior['metrics']:existing.add((r['case'],r['seed'],r['group']))
 jobs=[r for r in manifest if (r['case'],r['seed'],r['group']) not in existing and not (SAVED/(f"{r['case']}_s{r['seed']}_{r['group']}"+'.json')).exists()]
 batch=jobs[start:stop]
 print('BATCH',start,stop,'jobs',len(batch),'still',len(jobs),'cpu',os.cpu_count(),flush=True)
 # Preflight CU: CPU standard cheap; cap at 100 incremental CU based on 1367.69 start baseline, but other active assignments spend too.
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  futs={pool.submit(do_one,r):r for r in batch}
  for f in concurrent.futures.as_completed(futs):
   try:print('RESULT',f.result(),flush=True)
   except BaseException as e:print('ERROR',futs[f],repr(e),traceback.format_exc(),flush=True)

if __name__=='__main__':
 mode=os.environ.get('A3_B_MODE','prepare')
 if mode=='prepare':prepare()
 elif mode=='run':run_batch(0,int(os.environ.get('A3_B_BATCH','12')))
