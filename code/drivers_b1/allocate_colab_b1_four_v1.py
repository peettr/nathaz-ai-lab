#!/usr/bin/env python3
"""Bounded A100 capacity wait; never reuse another session."""
import datetime as dt
import json
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent
config = root / 'colab_state_B1_four.json'
log = root / 'ALLOCATION_B1_FOUR_v1.jsonl'
name = 'r234c-gc37x-b1-four'
for attempt in range(1, 8):
    argv = ['colab', '--auth', 'oauth2', '--config', str(config), 'new', '-s', name, '--gpu', 'A100']
    result = subprocess.run(argv, capture_output=True, text=True, timeout=100,
                            cwd='./23_AI_Weather/11_Subprojects/R23.4')
    text = result.stdout + result.stderr
    code = '503' if 'Service Unavailable' in text else '412' if 'Precondition Failed' in text else 'other'
    record = {'time_est': dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).isoformat(),
              'attempt': attempt, 'returncode': result.returncode, 'category': code,
              'output_tail': text[-900:]}
    with log.open('a') as f:
        f.write(json.dumps(record) + '\n')
    print('ALLOCATION', attempt, result.returncode, code, flush=True)
    if result.returncode == 0:
        print('ASSIGNED', name, flush=True)
        break
    if code not in ('503', '412'):
        raise RuntimeError('unexpected allocation error; inspect log')
    if attempt < 7:
        time.sleep(300)
