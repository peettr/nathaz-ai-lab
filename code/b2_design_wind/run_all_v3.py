#!/usr/bin/env python3
"""Exclusive, resumable only by batch artifacts manually; never relaunch automatically."""
import os, pathlib, subprocess, sys, time, json, traceback
root=pathlib.Path('/content/b2');lock=root/'b2_run_v3.lock';done=root/'b2_run_v3.exit.json'
with lock.open('x') as f:f.write(f'pid={os.getpid()}\nstarted={time.time()}\n')
start=time.time();log=root/'b2_run_v3.log'
with log.open('x',buffering=1) as f:
 rc=0
 for catalog in ('raft','storm'):
  print(f'START {catalog} {time.time()}',file=f,flush=True)
  p=subprocess.run([sys.executable,str(root/'run_catalog_v3.py'),'--catalog',catalog,'--batch','1000'],stdout=f,stderr=subprocess.STDOUT)
  print(f'END {catalog} exit={p.returncode} {time.time()}',file=f,flush=True)
  if p.returncode:rc=p.returncode;break
 done.write_text(json.dumps({'exit_code':rc,'wall_seconds':time.time()-start,'finished':time.time()}))
print('COMPLETE',rc)
