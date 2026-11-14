#!/usr/bin/env python3
"""One-owner bounded monitor; transfer each completed cycle, no replay."""
import datetime as dt, json, pathlib, subprocess, sys, time
B=pathlib.Path(__file__).resolve().parent
CFG=B/'colab_state_v2.json'; S='r234c-gc37-v2'
R='/content/r234c_gc37_v2'
C=['colab','--auth','oauth2','--config',str(CFG)]
CYCLES=['2020060806','2020060706','2020060606']
CUTOFF=dt.datetime(2026,11,13,8,18,tzinfo=dt.timezone(dt.timedelta(hours=-5)))

def cmd(args,timeout=150):
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 print('COMMAND',args[:7],p.returncode,p.stdout[-900:],p.stderr[-300:],flush=True)
 if p.returncode:raise RuntimeError((args,p.returncode,p.stdout[-1000:],p.stderr[-1000:]))
 return p.stdout

def probe():
 code="import pathlib,json; r=pathlib.Path('%s'); print(json.dumps({'manifests':[p.name for p in r.glob('RAW_MANIFEST_*.json')],'done':(r/'infer_gc37_v2.done').exists(),'failed':(r/'infer_gc37_v2.failed').read_text() if (r/'infer_gc37_v2.failed').exists() else None,'log':(r/'infer_gc37_v2.log').read_text()[-1000:]}))"%R
 p=subprocess.run(C+['exec','-s',S,'--timeout','90'],input=code+'\n',text=True,capture_output=True,timeout=130)
 if p.returncode:raise RuntimeError(('probe',p.stdout[-1000:],p.stderr[-1000:]))
 return json.loads(next(x for x in p.stdout.splitlines() if x.startswith('{')))

for cycle in CYCLES:
 while True:
  now=dt.datetime.now(dt.timezone(dt.timedelta(hours=-5)))
  if now>=CUTOFF:
   print('BUDGET_CUTOFF',now.isoformat(),'no new transfer; preserve existing outputs',flush=True)
   sys.exit(2)
  state=probe();print('STATE',now.isoformat(),state,flush=True)
  if state['failed']:raise RuntimeError(('worker_failed',state['failed']))
  if f'RAW_MANIFEST_{cycle}.json' in state['manifests']:break
  time.sleep(120)
 print('TRANSFER_BEGIN',cycle,flush=True)
 cmd([sys.executable,str(B/'transfer_gc37_cycle_v2.py'),cycle],timeout=1800)
 print('TRANSFER_DONE',cycle,flush=True)
print('ALL_RAW_DURABLE',dt.datetime.now().isoformat(),flush=True)
