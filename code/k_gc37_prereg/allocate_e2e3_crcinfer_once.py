#!/usr/bin/env python3
"""Bounded capacity wait for the single approved E2/E3 A100 session."""
import datetime as dt
import json
import pathlib
import subprocess
import time
R=pathlib.Path('./23_AI_Weather/06_Logs/k_gc37_prereg')
state=str(R/'colab_state_e2e3_crcinfer_25cu.json')
name='r234c-gc37-e2e3-crcinfer-25cu'
log=R/'ALLOCATION_E2E3_CRCINFER.jsonl'
for i in range(1,9):
    # Do not reallocate a named session that has already appeared.
    sessions=subprocess.run(['colab','--auth','oauth2','--config',state,'sessions'],capture_output=True,text=True,timeout=60)
    if name in sessions.stdout:
        print('EXISTING_OWN_SESSION',name,flush=True)
        break
    p=subprocess.run(['colab','--auth','oauth2','--config',state,'new','-s',name,'--gpu','A100'],capture_output=True,text=True,timeout=100)
    output=p.stdout+'\n'+p.stderr
    code='503' if 'Service Unavailable' in output else ('412' if 'Precondition Failed' in output else 'other')
    row={'time_est':dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).isoformat(),'attempt':i,'returncode':p.returncode,'http_class':code,'tail':output[-700:]}
    with log.open('a') as f:f.write(json.dumps(row)+'\n')
    print('ATTEMPT',i,'returncode',p.returncode,'class',code,flush=True)
    if p.returncode==0:break
    if code not in ('503','412'):break
    if i<8:time.sleep(360)
