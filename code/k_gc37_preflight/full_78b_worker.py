#!/usr/bin/env python3
"""One-session serial stage→three-cycle run; failures stop without retry."""
import datetime, json, pathlib, subprocess, sys, time, hashlib
R=pathlib.Path('/content/r234c_gc37_78b7088f');R.mkdir(exist_ok=True)
log=R/'worker_78b.log'
def emit(*a):
 with log.open('a') as h:print(datetime.datetime.now().isoformat(),*a,file=h,flush=True)
def stage(name,cmd):
 emit('START',name,cmd)
 with (R/f'{name}.log').open('x') as h:
  p=subprocess.run(cmd,stdout=h,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 emit('END',name,p.returncode)
 if p.returncode:raise RuntimeError((name,p.returncode))
try:
 stage('weights',['python3','/content/stage_gc37_weights_78b.py'])
 for cycle in ('2020060806','2020060706','2020060606'):
  steps={'2020060806':5,'2020060706':9,'2020060606':13}[cycle]
  stage('prepare_'+cycle,['python3','/content/prepare_gc37_gfs.py','--cycle',cycle,'--case','zero','--root',str(R)])
  stage('qa_t0_'+cycle,['python3','/content/qa_t0_gfs.py','--cycle',cycle,'--root',str(R)])
  stage('infer_'+cycle,['python3','/content/run_gc37_full.py','--cycle',cycle,'--case','zero','--run-tag','full','--steps',str(steps),'--root',str(R)])
  stage('wps_'+cycle,['python3','/content/build_gc37_wps.py','--cycle',cycle])
 emit('SUCCESS_ALL')
 (R/'worker_78b.done').write_text('SUCCESS_ALL\n')
except Exception as exc:
 emit('FAILED',repr(exc));(R/'worker_78b.failed').write_text(repr(exc)+'\n')
 raise
