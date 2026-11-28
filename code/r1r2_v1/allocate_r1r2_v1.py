#!/usr/bin/env python3
"""Bounded A100 capacity retry, never duplicate a live session."""
import datetime as dt
import json
from pathlib import Path
import subprocess
import time

R = Path(__file__).resolve().parent
STATE = str(R / 'colab_state_r1r2_v1.json')
NAME = 'r234c-gc37-r1r2-v1'
LOG = R / 'ALLOCATION_R1R2_V1.jsonl'
CWD = './23_AI_Weather/11_Subprojects/R23.4c'
for attempt in range(1, 9):
    global_sessions = subprocess.run(['colab', '--auth', 'oauth2', 'sessions'], capture_output=True, text=True, timeout=90)
    if NAME in global_sessions.stdout:
        private = subprocess.run(['colab', '--auth', 'oauth2', '--config', STATE, 'sessions'], capture_output=True, text=True, timeout=90)
        if NAME not in private.stdout:
            raise RuntimeError('Session name belongs to another registry; refuse to touch')
        print('OWN_SESSION_ALREADY_PRESENT', NAME, flush=True)
        break
    proc = subprocess.run(['colab', '--auth', 'oauth2', '--config', STATE, 'new', '-s', NAME, '--gpu', 'A100'], cwd=CWD, capture_output=True, text=True, timeout=120)
    msg = proc.stdout + '\n' + proc.stderr
    code = '503' if 'Service Unavailable' in msg else ('412' if 'Precondition Failed' in msg else 'other')
    row = {'time_est': dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).isoformat(), 'attempt': attempt, 'returncode': proc.returncode, 'http_class': code, 'tail': msg[-700:]}
    with LOG.open('a') as f:
        f.write(json.dumps(row) + '\n')
    print('ATTEMPT', attempt, 'returncode', proc.returncode, 'class', code, flush=True)
    if proc.returncode == 0:
        break
    if code not in ('503', '412'):
        raise RuntimeError(('unexpected allocation error', row))
    if attempt < 8:
        time.sleep(360)
else:
    print('CAPACITY_UNAVAILABLE_AFTER_EIGHT_TRIES', flush=True)
