#!/usr/bin/env python3
"""Exclusive detached stage wrapper; writes terminal status even on failure."""
import json, subprocess, sys, time, traceback
from pathlib import Path
source=sys.argv[1]
if source not in ('GRAP_v100_IFS','PANG_v100_IFS'):raise ValueError(source)
base=Path('/content/r237m1v2')
exit_path=base/f'{source}_exit_v1.json'
done=base/f'{source}_done_v1'
if exit_path.exists() or done.exists():raise FileExistsError('Stage already finished')
t=time.time()
try:
    p=subprocess.run([sys.executable,'/content/m1_worker_v2.py','collect','--source',source],check=False)
    code=p.returncode
except BaseException:
    traceback.print_exc();code=99
with exit_path.open('x') as f:json.dump({'source':source,'exit_code':code,'started_epoch':t,'ended_epoch':time.time(),'elapsed_s':time.time()-t},f)
done.touch(exist_ok=False)
sys.exit(code)
