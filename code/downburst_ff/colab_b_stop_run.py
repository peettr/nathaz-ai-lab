"""Colab-only A3-B stop matrix continuation; immutable prior 26, per-case checkpoints."""
import os,sys,json,time,subprocess,concurrent.futures,traceback
from pathlib import Path
P=Path('/content/a3_b_stop_1015');sys.path.insert(0,str(P/'code'))
import segment_b_run as b,segment_a_run as a
from wind_field_probe import CASES
from analyze_segment_b import read_out,measures
b.BASE=P/'base';b.ROOT=P/'runs';b.SRC=P/'base/ff_smoke_feedback';b.FAST=P/'bin/openfast';b.LIB=P/'base/rosco210_ff_build_guo_v2/libdiscon.so';a.CURVE=P/'base/segment_a_v4_curve.txt'
SAVED=P/'results';SAVED.mkdir(exist_ok=True);b.ROOT.mkdir(exist_ok=True)
GROUPS=b.GROUPS

def prepare():
 for case in CASES:
  for seed in b.SEEDS:
   target=b.ROOT/f'{case.name}_s{seed}'
   if target.exists():
    p=json.loads((target/'provenance.json').read_text());assert '14 x 0.5' in p['bts_phase_correction']
    continue
   target.mkdir();p=b.make_seed(case,seed,target)
   b.phase_correct_bts(target/'wind.bts',target/'corrected.bts')
   (target/'wind.bts').rename(target/'wind_unshifted.bts');(target/'corrected.bts').rename(target/'wind.bts')
   p['bts_phase_correction']='14 x 0.5 s initial frames inserted; OpenFAST t+7s correction'
   (target/'provenance.json').write_text(json.dumps(p,indent=2))
   print('generated',case.name,seed,flush=True)
 manifest=[]
 for case in CASES:
  for seed in b.SEEDS:
   target=b.ROOT/f'{case.name}_s{seed}';p=json.loads((target/'provenance.json').read_text())
   for group in GROUPS:
    when=p['trigger_abs_s'][group]
    manifest.append(dict(case=case.name,seed=seed,group=group,trigger_abs_s=when,actual_lead_s=p['rotor_3s_first25_abs_s']-when if when is not None else None,start_abs_s=p['start_abs_s'],end_abs_s=p['end_abs_s'],source=str(target)))
 f=SAVED/'manifest.json'
 if f.exists():assert json.loads(f.read_text())==manifest
 else:f.write_text(json.dumps(manifest,indent=2))
 print('PREPARED',len(manifest),flush=True)

def do_one(row,parity=False):
 key=f"{row['case']}_s{row['seed']}_{row['group']}";metricfile=SAVED/(key+('_parity' if parity else '')+'.json')
 if metricfile.exists():return key,'exists',0.
 if row['trigger_abs_s'] is None:
  entry=dict(row,returncode=-2,error='no upstream detection');metricfile.write_text(json.dumps(entry));return key,-2,0.
 dest=b.stage(row)
 p=json.loads((Path(row['source'])/'provenance.json').read_text())
 a.replace_key(dest/'NREL-5MW.fst','OutFileFmt','1')
 a.replace_key(dest/'NREL-5MW.fst','TStart',f"{max(0.,p['rotor_3s_first13_abs_s']-row['start_abs_s']-5):.3f}")
 env=os.environ.copy();env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(a.CURVE),ROSCO_FF_GAIN_DEG_PER_MS='0',OMP_NUM_THREADS='1')
 t0=time.monotonic()
 with (dest/'openfast.log').open('w') as log:
  try:rc=subprocess.run([str(b.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900).returncode
  except subprocess.TimeoutExpired:rc=-999
 wall=time.monotonic()-t0
 entry=dict(row,runroot=str(dest),returncode=rc,wall_s=round(wall,3),parity=parity)
 if rc==0:
  d=read_out(dest/'NREL-5MW.out');assert abs(d['Time'][-1]-(row['end_abs_s']-row['start_abs_s']))<.051
  entry['metrics']=measures(d,p,row['start_abs_s']);entry['first_output_s']=float(d['Time'][0])
  if row['seed']==112 and row['group'] in ('G1_instant','G2_real_1D','G4_T5'):
   import numpy as np
   np.savez_compressed(SAVED/(key+'.npz'),**{k:d[k][::10] for k in d})
 else:entry['log_tail']=(dest/'openfast.log').read_text(errors='replace')[-2500:]
 metricfile.write_text(json.dumps(entry,indent=2))
 print('DONE',key,rc,round(wall,1),flush=True)
 return key,rc,wall

def main():
 prepare()
 manifest=json.loads((SAVED/'manifest.json').read_text())
 prior=json.loads((P/'prior_26.json').read_text());existing={(r['case'],r['seed'],r['group']) for r in prior['metrics']}
 assert len(existing)==26 and len(manifest)==96
 for row in manifest:
  if (row['case'],row['seed'],row['group']) in existing:
   p=json.loads((Path(row['source'])/'provenance.json').read_text())
   assert '14 x 0.5' in p['bts_phase_correction']
 if not (SAVED/'parity_ok.json').exists():
  row=next(r for r in manifest if (r['case'],r['seed'],r['group'])==('I_near',112,'G1_instant'))
  do_one(row,True)
  actual=json.loads((SAVED/'I_near_s112_G1_instant_parity.json').read_text())
  old=next(x for x in prior['metrics'] if (x['case'],x['seed'],x['group'])==('I_near',112,'G1_instant'))
  key='tower_resultant_max_kNm';delta=100*abs(actual['metrics'][key]-old['metrics'][key])/old['metrics'][key]
  print('PARITY_DELTA_PCT',delta,flush=True)
  assert delta<.5
  (SAVED/'parity_ok.json').write_text(json.dumps(dict(delta_pct=delta,old=old['metrics'][key],new=actual['metrics'][key])))
 jobs=[r for r in manifest if (r['case'],r['seed'],r['group']) not in existing and not (SAVED/(f"{r['case']}_s{r['seed']}_{r['group']}.json")).exists()]
 print('JOBS',len(jobs),'CPU',os.cpu_count(),flush=True)
 # parallel independent run roots; avoid oversubscribing FFT/OpenFAST.
 with concurrent.futures.ThreadPoolExecutor(max_workers=min(6,max(1,os.cpu_count()//2))) as pool:
  futs=[pool.submit(do_one,r) for r in jobs]
  for f in concurrent.futures.as_completed(futs):
   try:
    k,rc,wall=f.result();print('PROGRESS',k,rc,wall,flush=True)
   except BaseException:print('EXCEPTION',traceback.format_exc(),flush=True)
 ok=0;fail=[]
 for r in jobs:
  key=f"{r['case']}_s{r['seed']}_{r['group']}";f=SAVED/(key+'.json')
  if f.exists() and json.loads(f.read_text())['returncode']==0:ok+=1
  else:fail.append(key)
 summary=dict(old_successes=len(existing),new_successes=ok,expected=96,failed=fail)
 (SAVED/'completion.json').write_text(json.dumps(summary,indent=2));print('COMPLETE',summary,flush=True)
if __name__=='__main__':main()
