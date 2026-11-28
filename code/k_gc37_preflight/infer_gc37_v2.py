#!/usr/bin/env python3
"""Serial three-cycle GPU inference. Never overwrite or silently retry a stage."""
import datetime, hashlib, json, pathlib, subprocess, sys
R=pathlib.Path('/content/r234c_gc37_v2'); R.mkdir(exist_ok=True)
LOG=R/'infer_gc37_v2.log'
def emit(*args):
 with LOG.open('a') as f: print(datetime.datetime.now().isoformat(),*args,file=f,flush=True)
def stage(name,cmd):
 emit('STAGE_START',name)
 with (R/(name+'.log')).open('x') as f:
  p=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
 emit('STAGE_END',name,p.returncode)
 if p.returncode: raise RuntimeError((name,p.returncode))
try:
 stage('weights',['python3','/content/stage_gc37_weights_v2.py'])
 for cycle,steps in [('2020060806',5),('2020060706',9),('2020060606',13)]:
  stage('prepare_'+cycle,['python3','/content/prepare_gc37_gfs.py','--cycle',cycle,'--case','zero','--root',str(R)])
  stage('qa_t0_'+cycle,['python3','/content/qa_t0_gfs.py','--cycle',cycle,'--root',str(R)])
  stage('infer_'+cycle,['python3','/content/run_gc37_raw_v2.py','--cycle',cycle,'--case','zero','--run-tag','full','--steps',str(steps),'--root',str(R)])
  out=R/f'forecast_{cycle}_full_{steps}step'; files=sorted(out.glob('step_*.npz'))
  assert len(files)==steps,(cycle,len(files),steps)
  manifest=[{'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()} for p in files]
  (R/f'RAW_MANIFEST_{cycle}.json').write_text(json.dumps(manifest,indent=2))
  emit('RAW_READY',cycle,len(files),sum(x['bytes'] for x in manifest))
 (R/'infer_gc37_v2.done').write_text('SUCCESS\n');emit('SUCCESS_ALL')
except Exception as e:
 emit('FAILED',repr(e));(R/'infer_gc37_v2.failed').write_text(repr(e)+'\n');raise
