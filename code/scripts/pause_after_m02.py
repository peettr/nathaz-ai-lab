"""Pause old orchestrator only after m02's verified upload and stop.
This guard allows an operator to patch and resume at the m03 boundary.
"""
import json, os, signal, time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
pid=2953162
log=root/'orchestrator.jsonl'
while True:
    if not Path(f'/proc/{pid}').exists():
        print('ORCHESTRATOR_EXITED', flush=True);break
    rows=log.read_text().splitlines()[-5:]
    if any((lambda x:x.get('event')=='STOPPED' and x.get('session')=='wx-cnew-m02-1015')(json.loads(row)) for row in rows):
        os.kill(pid,signal.SIGSTOP)
        print('PAUSED_AFTER_M02_STOP',flush=True)
        break
    time.sleep(.025)
