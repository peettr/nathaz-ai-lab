"""Post-amendment stationary-only continuation; old storm failure remains immutable."""
import os,sys,time,json,subprocess,tarfile,traceback
from pathlib import Path
P=Path('/content/a3_d_yawfix_r2_full'); R=P/'results'
assert (P/'d_pipeline.failed').exists() and not (P/'d_pipeline.done').exists()
assert len(list(R.glob('I_near_s*_*.json')))==120
assert len(list(R.glob('III_kzm05_s*_*.json')))==120
assert len(list(R.glob('III_kzm00_s*_*.json')))==120
assert not list(R.glob('NTM_*.json')) and not list((P/'runs').glob('NTM_*'))
log=P/'stationary_continue_r2.log'; assert not log.exists()
with log.open('x',buffering=1) as f:
 try:
  for stage in ('stationary_prep','stationary_yaw','stationary_rules'):
   print('START',stage,time.strftime('%Y-%m-%d %H:%M:%S'),file=f,flush=True)
   rc=subprocess.run([sys.executable,'-u','/content/colab_d_full_r2.py',stage],stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','R2_YAW_RATE':'0.004188790204786391'}).returncode
   print('END',stage,'RC',rc,time.strftime('%Y-%m-%d %H:%M:%S'),file=f,flush=True)
   if rc:raise RuntimeError(f'{stage} failed {rc}')
   if stage=='stationary_yaw':
    rows=[json.loads(x.read_text()) for x in R.glob('NTM_*_NoStop.json')]
    assert len(rows)==36 and all(x['returncode']==0 for x in rows)
    over=[(x['case'],x['seed'],x['yaw_rate_max_deg_s']) for x in rows if x['yaw_rate_max_deg_s']>.31]
    print('STATIONARY_RATE_GATE',len(rows),'max',max(x['yaw_rate_max_deg_s'] for x in rows),'over',over,file=f,flush=True)
    if over:raise RuntimeError(f'stationary yaw rate exceeded: {over}')
  assert len(json.loads((R/'stationary_rules_all.json').read_text()))==36
  (P/'stationary_continue_r2.done').write_text('stationary 36/36 success\n')
 except BaseException:
  traceback.print_exc(file=f);(P/'stationary_continue_r2.failed').write_text(traceback.format_exc());raise
 finally:
  with tarfile.open(P/'stationary_checkpoint_r2.tar.gz','w:gz') as z:
   for x in R.glob('*.json'):z.add(x,arcname=x.name)
