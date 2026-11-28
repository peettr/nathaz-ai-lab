#!/usr/bin/env python3
"""Bounded A100 availability retry; never relaunch an allocated session."""
import datetime as dt,json,pathlib,subprocess,time
B=pathlib.Path('./23_AI_Weather/06_Logs/k_gc37_prereg')
CFG=B/'colab_state_e2e3_25cu.json';NAME='r234c-gc37-e2e3-25cu'
C=['colab','--auth','oauth2']
out=B/'ALLOCATION_E2E3_25CU.jsonl'
if out.exists():raise FileExistsError(out)
with out.open('x') as f:
 for attempt in range(1,9):
  prior=subprocess.run(C+['--config',str(CFG),'sessions'],capture_output=True,text=True,timeout=45)
  global_list=subprocess.run(C+['sessions'],capture_output=True,text=True,timeout=45)
  if NAME in global_list.stdout or NAME in prior.stdout:
   rec={'attempt':attempt,'time':dt.datetime.now().astimezone().isoformat(),'state':'SESSION_ALREADY_LISTED_STOP','private':prior.stdout[-300:],'global':global_list.stdout[-300:]}
   f.write(json.dumps(rec)+'\n');f.flush();raise SystemExit('Session already listed; inspect ownership before any action')
  p=subprocess.run(C+['--config',str(CFG),'new','-s',NAME,'--gpu','A100'],cwd='./23_AI_Weather/11_Subprojects/R23.4',capture_output=True,text=True,timeout=90)
  rec={'attempt':attempt,'time':dt.datetime.now().astimezone().isoformat(),'returncode':p.returncode,'stdout_tail':p.stdout[-1200:],'stderr_tail':p.stderr[-1200:]}
  f.write(json.dumps(rec)+'\n');f.flush();print('ALLOCATION',attempt,rec['returncode'],rec['time'],flush=True)
  if p.returncode==0:
   print('ALLOCATED',NAME,flush=True);break
  if 'Service Unavailable' not in p.stderr and 'Precondition Failed' not in p.stderr and 'Allocation refused' not in p.stderr:
   raise SystemExit('Unexpected allocation error; no blind retry')
  if attempt<8:time.sleep(300)
 else:raise SystemExit('A100 unavailable after eight bounded attempts')
