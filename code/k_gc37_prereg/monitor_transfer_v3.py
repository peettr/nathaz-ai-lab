#!/usr/bin/env python3
"""Single-owner, durable v3 cycle handoff and 10-CU stop gate."""
import datetime as dt, json, pathlib, subprocess, sys, time
B=pathlib.Path(__file__).resolve().parent
C=['colab','--config',str(B/'colab_state_v3.json')]
S='r234c-gc37-v3'; R='/content/r234c_gc37_v3'
CUTOFF=dt.datetime(2026,11,14,4,9,tzinfo=dt.timezone(dt.timedelta(hours=-5)))
CYCLES=['2020060806','2020060706','2020060606']
def cmd(args,timeout=180):
    p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    print('COMMAND',args[:5],p.returncode,p.stdout[-700:],p.stderr[-350:],flush=True)
    if p.returncode:raise RuntimeError((args[:5],p.returncode,p.stdout[-500:],p.stderr[-500:]))
    return p.stdout
def probe():
    code="import pathlib,json; r=pathlib.Path('%s'); print(json.dumps({'manifests':[p.name for p in r.glob('RAW_MANIFEST_*.json')],'done':(r/'infer_gc37_v3.done').exists(),'failed':(r/'infer_gc37_v3.failed').read_text() if (r/'infer_gc37_v3.failed').exists() else None,'log':(r/'infer_gc37_v3.log').read_text()[-700:] if (r/'infer_gc37_v3.log').exists() else ''}))"%R
    p=subprocess.run(C+['exec','-s',S,'--timeout','45'],input=code+'\n',capture_output=True,text=True,timeout=70)
    if p.returncode:raise RuntimeError(('probe',p.stdout[-400:],p.stderr[-400:]))
    return json.loads(next(x for x in p.stdout.splitlines() if x.startswith('{')))
try:
    for cycle in CYCLES:
        while True:
            now=dt.datetime.now(dt.timezone(dt.timedelta(hours=-5)))
            if now>=CUTOFF:raise RuntimeError(('CU_CUTOFF',now.isoformat()))
            state=probe();print('STATE',now.isoformat(),state,flush=True)
            if state['failed']:raise RuntimeError(('inference_failed',state['failed']))
            if f'RAW_MANIFEST_{cycle}.json' in state['manifests']:break
            time.sleep(90)
        print('TRANSFER_BEGIN',cycle,flush=True)
        cmd([sys.executable,str(B/'transfer_gc37_cycle_v3.py'),cycle],timeout=2100)
        print('TRANSFER_DONE',cycle,flush=True)
    print('ALL_RAW_DURABLE',flush=True)
finally:
    # Stop even on failure/cutoff; raw assets already transferred remain immutable.
    try:
        cmd(C+['stop','-s',S],timeout=100)
        print('COLAB_STOPPED',flush=True)
    except Exception as e:print('STOP_NEEDS_MANUAL_CHECK',repr(e),flush=True)
