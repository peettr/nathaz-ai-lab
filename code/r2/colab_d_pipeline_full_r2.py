"""Remote bounded Colab pipeline with periodic small metric-only checkpoints."""
import subprocess,sys,time,tarfile,os,threading,traceback
from pathlib import Path
P=Path('/content/a3_d_yawfix_r2_full');R=P/'results'
STAGES=['storm_prep','storm_base','build_rules','storm_rules','stationary_prep','stationary_yaw','stationary_rules']
stop=threading.Event()
def checkpoint():
 while not stop.wait(180):
  try:
   tmp=P/'d_checkpoint_new.tar.gz'
   with tarfile.open(tmp,'w:gz') as z:
    for f in R.glob('*.json'):z.add(f,arcname=f.name)
   os.replace(tmp,P/'d_checkpoint.tar.gz')
  except Exception:traceback.print_exc()
threading.Thread(target=checkpoint,daemon=True).start()
with (P/'d_pipeline.log').open('a',buffering=1) as log:
 try:
  for stage in STAGES:
   print('START',stage,time.strftime('%Y-%m-%d %H:%M:%S'),file=log,flush=True)
   rc=subprocess.run([sys.executable,'-u','/content/colab_d_full_r2.py',stage],stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','R2_YAW_RATE':'0.004188790204786391'}).returncode
   print('END',stage,'RC',rc,time.strftime('%Y-%m-%d %H:%M:%S'),file=log,flush=True)
   if rc:raise RuntimeError(stage+' failed '+str(rc))
   if stage in ('storm_base','storm_rules','stationary_yaw'):
    import json
    vals=[(f.name,json.loads(f.read_text()).get('yaw_rate_max_deg_s')) for f in R.glob('*.json') if '_s' in f.name and not f.name.endswith('_rules.json')]
    over=[(name,v) for name,v in vals if v is not None and v>.31]
    print('RATE_GATE',stage,'checked',len(vals),'max',max((v for _,v in vals if v is not None),default=None),'over',over[:10],file=log,flush=True)
    if over:raise RuntimeError('yaw rate gate failed '+str(over[:10]))
  (P/'d_pipeline.done').write_text('success all stages\n')
 except Exception:
  traceback.print_exc(file=log);(P/'d_pipeline.failed').write_text(traceback.format_exc());raise
 finally:
  stop.set();checkpoint.__globals__['stop'].clear() if False else None
  tmp=P/'d_checkpoint_new.tar.gz'
  with tarfile.open(tmp,'w:gz') as z:
   for f in R.glob('*.json'):z.add(f,arcname=f.name)
  os.replace(tmp,P/'d_checkpoint.tar.gz')
