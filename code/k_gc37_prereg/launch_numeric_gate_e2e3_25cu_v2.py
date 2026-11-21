#!/usr/bin/env python3
"""One-shot VM setup and numerical input gate; never starts inference."""
import datetime as dt
import json
import pathlib
import subprocess
import sys
import traceback

root = pathlib.Path('/content/r234c_gc37_E2E3')
root.mkdir(exist_ok=True)
exit_path = root / 'numeric_gate_worker.exit.json'
if exit_path.exists():
    raise FileExistsError(exit_path)
try:
    for stage, args in (
        ('setup', [sys.executable, '/content/setup_gc37_vm_e2e3.py']),
        ('numeric_gate', [sys.executable, '/content/numeric_gate_e2e3_v2.py', '--root', str(root)]),
    ):
        print('STAGE_START', stage, dt.datetime.now(dt.timezone.utc).isoformat(), flush=True)
        result = subprocess.run(args, check=False)
        print('STAGE_END', stage, result.returncode, dt.datetime.now(dt.timezone.utc).isoformat(), flush=True)
        if result.returncode:
            raise RuntimeError(f'{stage} exited {result.returncode}')
    status = {'status': 'gate_pass', 'time_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
except BaseException as exc:
    traceback.print_exc()
    status = {'status': 'gate_failed', 'error': repr(exc), 'time_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
exit_path.write_text(json.dumps(status))
print('WORKER_DONE', status, flush=True)
