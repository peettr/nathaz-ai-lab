#!/usr/bin/env python3
"""Stop only owned L26.14 v2 A100 at completion or before budget ceiling."""
import json
from pathlib import Path
import subprocess
import time
import datetime
p=Path('./26_Quick_Trials/06_Logs/L26.14/v2')
config=p/'colab_state.json'
state=Path('./platform/colab-keepalive/l2614v2quick.json')
base=['colab','--auth','oauth2','--config',str(config)]
start=datetime.datetime.fromisoformat('2026-10-29T08:58:04-04:00').timestamp()
deadline=start+75*60  # ~6.75 CU at 5.4 CU/hour; margin under 8 CU
while True:
    s=json.loads(state.read_text()) if state.exists() else {}
    print(datetime.datetime.now().astimezone().isoformat(),s.get('state'),s.get('last',{}).get('files'),flush=True)
    if s.get('state')=='done':break
    if time.time()>=deadline:
        print('BUDGET_STOP',flush=True)
        for lab in 'AB':
            target=p/f'budget_partial_{lab}.jsonl'
            if not target.exists():
                subprocess.run(base+['download','-s','l2614v2quick',f'/content/l26v2/answers_{lab}.jsonl',str(target)],timeout=100)
        break
    if s.get('state') in ('session_gone','final_pull_failed','max_hours','job_ended_no_marker','log_stale'):
        print('KEEPALIVE_TERMINAL',s.get('state'),flush=True)
        break
    time.sleep(120)
print('STOP owned session',flush=True)
r=subprocess.run(base+['stop','-s','l2614v2quick'],text=True,capture_output=True,timeout=90)
print('stop',r.returncode,r.stdout,r.stderr,flush=True)
r=subprocess.run(base+['sessions'],text=True,capture_output=True,timeout=90)
print('sessions',r.returncode,r.stdout,r.stderr,flush=True)
