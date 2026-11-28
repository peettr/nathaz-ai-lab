#!/usr/bin/env python3
"""Bounded allocation for the approved D-X1 session only."""
import datetime as dt
import json
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent
config = root / 'colab_state_B1_four_DX1.json'
log = root / 'ALLOCATION_B1_FOUR_DX1_v2.jsonl'
name = 'r234c-gc37x-b1-four-dx1'
for attempt in range(2, 9):
    sessions = subprocess.run(['colab', '--auth', 'oauth2', 'sessions'], capture_output=True, text=True, timeout=90)
    if name in sessions.stdout:
        raise RuntimeError('session already active; inspect owner before using')
    argv = ['colab', '--auth', 'oauth2', '--config', str(config), 'new', '-s', name, '--gpu', 'A100']
    result = subprocess.run(argv, capture_output=True, text=True, timeout=120,
                            cwd='./23_AI_Weather/11_Subprojects/R23.4')
    text = result.stdout + result.stderr
    category = '503' if 'Service Unavailable' in text else '412' if 'Precondition Failed' in text else 'other'
    record = {'time_est': dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).isoformat(),
              'attempt': attempt, 'returncode': result.returncode, 'category': category,
              'output_tail': text[-900:]}
    with log.open('a') as f:
        f.write(json.dumps(record) + '\n')
    print('ALLOCATION', attempt, result.returncode, category, flush=True)
    if result.returncode == 0:
        print('ASSIGNED', name, flush=True)
        break
    if category not in ('503', '412'):
        raise RuntimeError('unexpected allocation error; inspect log')
    if attempt < 8:
        time.sleep(300)
