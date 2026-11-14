#!/usr/bin/env python3
"""Bounded A100 capacity wait; success creates exactly one named session."""
import datetime, json, pathlib, subprocess, time
ROOT=pathlib.Path('./23_AI_Weather/06_Logs/k_gc37_preflight')
CONFIG=ROOT/'colab_state_v2.json'; NAME='r234c-gc37-v2'
BASE=['colab','--auth','oauth2']
LOG=ROOT/'ALLOCATION_V2_CAPACITY.jsonl'
time.sleep(300)  # last manual 503 was 05:55 EST; retry no sooner than five minutes later
for attempt in range(1,9):
    sessions=subprocess.run(BASE+['sessions'],capture_output=True,text=True,timeout=60)
    if sessions.returncode or NAME in sessions.stdout:
        raise RuntimeError(('session_list_failed_or_name_taken',attempt,sessions.returncode,sessions.stdout[-2000:],sessions.stderr[-1000:]))
    p=subprocess.run(BASE+['--config',str(CONFIG),'new','-s',NAME,'--gpu','A100'],capture_output=True,text=True,timeout=100)
    rec={'time':datetime.datetime.now().astimezone().isoformat(),'attempt':attempt,'returncode':p.returncode,'stdout_tail':p.stdout[-500:],'stderr_tail':p.stderr[-1200:]}
    with LOG.open('a') as f:f.write(json.dumps(rec)+'\n')
    print(rec['time'],attempt,p.returncode,p.stdout[-200:],p.stderr[-200:],flush=True)
    if p.returncode==0:
        print('ALLOCATED',NAME,flush=True)
        break
    if 'Service Unavailable' not in p.stdout+p.stderr and 'Precondition Failed' not in p.stdout+p.stderr:
        raise RuntimeError(('unexpected_new_error',rec))
    if attempt<8:time.sleep(360)
else:raise RuntimeError('capacity_not_available_after_8_bounded_attempts')
