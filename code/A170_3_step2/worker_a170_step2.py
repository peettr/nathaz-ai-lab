"""Bounded Colab CPU worker: paired 2-degree shutdown experiment."""
import concurrent.futures, json, os, subprocess, sys, tarfile, threading, time, traceback
from pathlib import Path
sys.path.insert(0, '/content')
import colab_a170_step2 as m
P=m.P; R=P/'results'; LOG=Path('/content/a170_step2.log'); DEADLINE=time.monotonic()+2*3600+45*60
os.environ.update(R2_YAW_RATE='0.004188790204786391', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
stop=threading.Event()
def log(*args):
 print(time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime()),*args,flush=True)
def checkpoint():
 if not R.exists():return
 tmp=Path('/content/a170_checkpoint_new.tar.gz')
 with tarfile.open(tmp,'w:gz') as tf:
  for f in R.glob('*.json'):tf.add(f,arcname=f.name)
 os.replace(tmp,'/content/a170_checkpoint.tar.gz')
def periodic():
 while not stop.wait(180):
  try:checkpoint()
  except Exception:traceback.print_exc()
def run_rows(rows):
 def one(row):
  key=f"{row['case']}_s{row['seed']}_{row['group']}"
  if time.monotonic()>DEADLINE:return (key,'deadline')
  x=m.run_one(row)
  return (key,x['returncode'])
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  for key,rc in pool.map(one,rows):
   log('ROW',key,rc)
   if rc!='deadline' and rc!=0:raise RuntimeError(f'{key} returncode {rc}')
 if time.monotonic()>DEADLINE:raise TimeoutError('3h allocation deadline approaching')
 checkpoint()
def row(case,seed,group,trigger):
 root=P/'runs'/f'{case}_s{seed}';p=json.loads((root/'provenance.json').read_text())
 return dict(case=case,seed=seed,group=group,source=str(root),start_abs_s=p['start_abs_s'],end_abs_s=p['end_abs_s'],trigger_abs_s=trigger)
def main():
 log('SETUP');m.setup();checkpoint()
 log('STORM_PREP');m.storm_prep();checkpoint()
 smoke=row('I_near',112,'G1',json.loads((P/'runs/I_near_s112/provenance.json').read_text())['rotor_3s_first25_abs_s'])
 run_rows([smoke])
 os.environ['A170_SMOKE']='1';m.build_rules();os.environ.pop('A170_SMOKE')
 manifest=json.loads((R/'rules_manifest.json').read_text())
 g2=next(r for r in manifest if r['group']=='G2L')
 run_rows([g2]);pilot=json.loads((R/'I_near_s112_G2L.json').read_text())
 assert pilot['returncode']==0 and pilot['yaw_rate_max_deg_s']<=.31, 'smoke fails rate limit'
 (R/'smoke_acceptance.json').write_text(json.dumps(dict(case='I_near',seed=112,group='G2L',returncode=pilot['returncode'],yaw_rate_max_deg_s=pilot['yaw_rate_max_deg_s'],metrics=pilot['metrics']),indent=2))
 checkpoint();log('SMOKE_OK',pilot['yaw_rate_max_deg_s'])
 rows=[]
 for case in ('I_near','III_kzm05','III_kzm00'):
  for seed in m.SEEDS:
   if (case,seed)==('I_near',112):continue
   p=json.loads((P/'runs'/f'{case}_s{seed}'/'provenance.json').read_text())
   rows.append(row(case,seed,'G1',p['rotor_3s_first25_abs_s']))
 log('G1_START',len(rows));run_rows(rows)
 m.build_rules();manifest=json.loads((R/'rules_manifest.json').read_text());rows=[r for r in manifest if r['group']=='G2L']
 assert len(rows)==36
 log('G2L_START',len(rows));run_rows(rows)
 keys=[f'{case}_s{seed}_{group}' for case in ('I_near','III_kzm05','III_kzm00') for seed in m.SEEDS for group in ('G1','G2L')]
 vals=[json.loads((R/(k+'.json')).read_text()) for k in keys]
 assert len(vals)==72 and all(v['returncode']==0 for v in vals)
 over=[(k,v['yaw_rate_max_deg_s']) for k,v in zip(keys,vals) if v['yaw_rate_max_deg_s']>.31]
 (R/'batch_acceptance.json').write_text(json.dumps(dict(expected=72,completed=72,rate_over=over,rate_max=max(v['yaw_rate_max_deg_s'] for v in vals)),indent=2))
 checkpoint();log('SUCCESS',len(vals),'over',len(over))
if __name__=='__main__':
 threading.Thread(target=periodic,daemon=True).start()
 try:
  main();Path('/content/a170_step2.done').write_text('ok\n')
 except BaseException:
  traceback.print_exc();Path('/content/a170_step2.failed').write_text(traceback.format_exc())
 finally:
  stop.set()
  try:checkpoint()
  except Exception:traceback.print_exc()
