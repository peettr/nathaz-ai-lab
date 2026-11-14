"""Independent Colab replay of 26 legacy A3-B stop runs; no local solver."""
import os,sys,json,time,gzip,tarfile,shutil,subprocess,hashlib,concurrent.futures,traceback
from pathlib import Path
P=Path('/content/a3_b_v4c_1015')
def setup():
 P.mkdir(exist_ok=False)
 with tarfile.open('/content/a3_b_colab_bundle_1014.tar.gz') as f:f.extractall(P,filter='data')
 (P/'bin').mkdir()
 with gzip.open('/content/openfast_5_linux_1014.gz','rb') as f,(P/'bin/openfast').open('wb') as w:shutil.copyfileobj(f,w)
 (P/'bin/openfast').chmod(0o755)
 (P/'runs').mkdir();(P/'results').mkdir()
 print('OPENFAST',subprocess.run([str(P/'bin/openfast'),'-v'],capture_output=True,text=True).stdout[-350:],'CPU',os.cpu_count(),flush=True)
def modules():
 sys.path.insert(0,str(P/'code'))
 import segment_b_run as b,segment_a_run as a
 from wind_field_probe import CASES
 from analyze_segment_b import read_out,measures
 b.BASE=P/'base';b.ROOT=P/'runs';b.SRC=P/'base/ff_smoke_feedback';b.FAST=P/'bin/openfast';b.LIB=P/'base/rosco210_ff_build_guo_v2/libdiscon.so';a.CURVE=P/'base/segment_a_v4_curve.txt'
 return b,a,CASES,read_out,measures
def digest(f):
 h=hashlib.sha256()
 with f.open('rb') as v:
  for chunk in iter(lambda:v.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def prepare():
 b,a,CASES,_,_=modules();old=json.loads(Path('/content/prior_26_stop_1015.json').read_text())['metrics']
 assert len(old)==26 and len({(x['case'],x['seed'],x['group']) for x in old})==26
 assert {x['case'] for x in old}=={'I_near'} and {x['seed'] for x in old}=={112,203,317,419}
 manifest=[];hashes={}
 for case in CASES:
  if case.name!='I_near':continue
  for seed in sorted({x['seed'] for x in old}):
   root=P/'runs'/f'{case.name}_s{seed}';root.mkdir(exist_ok=False)
   p=b.make_seed(case,seed,root)
   b.phase_correct_bts(root/'wind.bts',root/'corrected.bts')
   (root/'wind.bts').rename(root/'wind_unshifted.bts');(root/'corrected.bts').rename(root/'wind.bts')
   p['bts_phase_correction']='14 x 0.5 s initial frames inserted; OpenFAST t+7s correction'
   (root/'provenance.json').write_text(json.dumps(p,indent=2))
   hashes[f'{case.name}_s{seed}']={'wind_bts_sha256':digest(root/'wind.bts'),'wind_unshifted_bts_sha256':digest(root/'wind_unshifted.bts'),'bytes':(root/'wind.bts').stat().st_size,'phase_correction':p['bts_phase_correction']}
   print('WIND',case.name,seed,hashes[f'{case.name}_s{seed}']['wind_bts_sha256'],flush=True)
 for x in old:
  root=P/'runs'/f"{x['case']}_s{x['seed']}";p=json.loads((root/'provenance.json').read_text());g=x['group'];when=p['trigger_abs_s'][g]
  manifest.append(dict(case=x['case'],seed=x['seed'],group=g,trigger_abs_s=when,actual_lead_s=p['rotor_3s_first25_abs_s']-when if when is not None else None,start_abs_s=p['start_abs_s'],end_abs_s=p['end_abs_s'],source=str(root)))
 (P/'results/manifest.json').write_text(json.dumps(manifest,indent=2));(P/'results/wind_hashes.json').write_text(json.dumps(hashes,indent=2))
 print('PREPARED',len(manifest),flush=True)
def one(row):
 b,a,_,read_out,measures=modules();key=f"{row['case']}_s{row['seed']}_{row['group']}";f=P/'results'/(key+'.json')
 if f.exists():return key,json.loads(f.read_text())['returncode']
 dest=b.stage(row);p=json.loads((Path(row['source'])/'provenance.json').read_text())
 a.replace_key(dest/'NREL-5MW.fst','OutFileFmt','1')
 a.replace_key(dest/'NREL-5MW.fst','TStart',f"{max(0.,p['rotor_3s_first13_abs_s']-row['start_abs_s']-5):.3f}")
 env=os.environ.copy();env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(a.CURVE),ROSCO_FF_GAIN_DEG_PER_MS='0',OMP_NUM_THREADS='1')
 t0=time.monotonic()
 with (dest/'openfast.log').open('w') as log:
  try:rc=subprocess.run([str(b.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900).returncode
  except subprocess.TimeoutExpired:rc=-999
 entry=dict(row,returncode=rc,wall_s=round(time.monotonic()-t0,3),wind_bts_sha256=digest(Path(row['source'])/'wind.bts'))
 if rc==0:
  d=read_out(dest/'NREL-5MW.out');assert abs(d['Time'][-1]-(row['end_abs_s']-row['start_abs_s']))<.051
  entry['metrics']=measures(d,p,row['start_abs_s']);entry['event_window_abs_s']=[p['rotor_3s_first13_abs_s'],p['rotor_3s_last25_abs_s']+60]
 else:entry['log_tail']=(dest/'openfast.log').read_text(errors='replace')[-2500:]
 f.write_text(json.dumps(entry,indent=2));print('DONE',key,rc,entry['wall_s'],flush=True);return key,rc
def run():
 manifest=json.loads((P/'results/manifest.json').read_text());assert len(manifest)==26
 with concurrent.futures.ThreadPoolExecutor(max_workers=min(6,max(1,os.cpu_count()//2))) as pool:
  futs=[pool.submit(one,r) for r in manifest]
  for f in concurrent.futures.as_completed(futs):
   try:print('PROGRESS',f.result(),flush=True)
   except BaseException:print('EXCEPTION',traceback.format_exc(),flush=True)
 rows=[]
 for r in manifest:
  f=P/'results'/(f"{r['case']}_s{r['seed']}_{r['group']}.json")
  if f.exists():rows.append(json.loads(f.read_text()))
 z=dict(expected=26,success=sum(x['returncode']==0 for x in rows),failed=[(x['case'],x['seed'],x['group']) for x in rows if x['returncode']!=0],missing=len(manifest)-len(rows))
 (P/'results/completion.json').write_text(json.dumps(z,indent=2));print('COMPLETE',z,flush=True)
if __name__=='__main__':{'setup':setup,'prepare':prepare,'run':run}[sys.argv[1]]()
