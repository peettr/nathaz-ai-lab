"""A170④ CPU-only checkpointed runner; old G1 metrics are never replaced."""
import json, os, sys, time, tarfile, threading, traceback, concurrent.futures
from pathlib import Path
sys.path.insert(0,'/content')
import colab_a170_4 as m
P=m.P; R=P/'results'; os.environ.update(R2_YAW_RATE='0.004188790204786391',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
stop=threading.Event()

def log(*x): print(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),*x,flush=True)
def checkpoint():
 if not R.exists(): return
 tmp=Path('/content/a170_4_checkpoint.tmp.tar.gz')
 with tarfile.open(tmp,'w:gz') as tf:
  for f in R.glob('*.json'):tf.add(f,arcname=f.name)
 tmp.replace('/content/a170_4_checkpoint.tar.gz')
def periodic():
 while not stop.wait(180):
  try:checkpoint()
  except Exception: traceback.print_exc()
def row(seed,group,hit):
 root=P/'runs'/f'I_near_s{seed}';p=json.loads((root/'provenance.json').read_text())
 return dict(case='I_near',seed=seed,group=group,source=str(root),start_abs_s=p['start_abs_s'],end_abs_s=p['end_abs_s'],trigger_abs_s=hit)
def run_rows(rows):
 def one(r):
  if r['trigger_abs_s'] is None:
   x=m.run_one(dict(r,trigger_abs_s=r['end_abs_s']+100),shutdown=False)
   x['trigger_abs_s']=None;x['not_triggered']=True
   (R/f"I_near_s{r['seed']}_{r['group']}.json").write_text(json.dumps(x,indent=2))
   return x
  return m.run_one(r)
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  for x in pool.map(one,rows):
   log('ROW',x['seed'],x['group'],x['returncode'],x.get('yaw_rate_max_deg_s'))
   if x['returncode']!=0:raise RuntimeError(f"solve failed {x['seed']} {x['group']}")
 checkpoint()
def main():
 log('SETUP');m.setup();checkpoint()
 base=json.loads(Path('/content/r2_reuse_I_near.json').read_text())
 assert len(base)==36
 c=m.case_list(m.mods()[2])[0][0]
 m.make_storm(c,'I_near',112)
 p=json.loads((P/'runs/I_near_s112/provenance.json').read_text())
 run_rows([row(112,'G1',p['rotor_3s_first25_abs_s'])])
 old=base['I_near_s112_G1.json'];new=json.loads((R/'I_near_s112_G1.json').read_text())
 diffs={k:abs(new['metrics'][k]-v)/max(abs(v),1e-12) for k,v in old['metrics'].items()}
 parity=dict(seed=112,max_relative_metric_difference=max(diffs.values()),field_relative_differences=diffs,old_rate=old['yaw_rate_max_deg_s'],new_rate=new['yaw_rate_max_deg_s'],passes=max(diffs.values())<.001)
 (R/'parity.json').write_text(json.dumps(parity,indent=2));checkpoint();log('PARITY',parity)
 assert parity['passes'],'r2 G1 parity >0.1%; stop before reuse'
 # Do not substitute regenerated metrics for r2: only its yaw time series drives the new moving sensor.
 run_rows([m.g2lc_row(112)])
 # Newly registered seeds: G1 first, then the paired fixed-3x3 G2 and moving-3x3 G2Lc.
 for seed in m.NEW_SEEDS:
  m.make_storm(c,'I_near',seed)
 log('FIELDS_NEW_READY',len(m.NEW_SEEDS));checkpoint()
 run_rows([row(s,'G1',json.loads((P/'runs'/f'I_near_s{s}'/'provenance.json').read_text())['rotor_3s_first25_abs_s']) for s in m.NEW_SEEDS])
 # G2 fixed-grid trigger uses the same up_ideal array and timing as r2 build_rules.
 b,_,_,_,_,_=m.mods()
 rows=[]
 for s in m.NEW_SEEDS:
  root=P/'runs'/f'I_near_s{s}';z=m.np.load(root/'signals.npz');p=json.loads((root/'provenance.json').read_text())
  t=z['t'];hit=b.first_cross(t[t<=p['end_abs_s']],z['up_ideal'][t<=p['end_abs_s']],25.)
  rows.append(row(s,'G2',hit))
 run_rows(rows)
 # Additional 11 original G1 yaw trajectories are NOT authorized by the frozen protocol.
 # Leave a checkpoint and explicitly mark pending rather than invent trajectories.
 (R/'phase1_done.json').write_text(json.dumps(dict(parity=parity,completed_new_seed_g1_g2=len(m.NEW_SEEDS),old_s112_g2lc=True,pending_new_g2lc_seeds=m.NEW_SEEDS,pending_old_g2lc_seeds=m.ORIGINAL_SEEDS[1:])))
 checkpoint();log('PHASE1_COMPLETE')
if __name__=='__main__':
 threading.Thread(target=periodic,daemon=True).start()
 try:main();Path('/content/a170_4_phase1.done').write_text('ok\n')
 except BaseException:traceback.print_exc();Path('/content/a170_4_phase1.failed').write_text(traceback.format_exc())
 finally:
  stop.set()
  try:checkpoint()
  except Exception:traceback.print_exc()
