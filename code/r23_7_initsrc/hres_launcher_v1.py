#!/usr/bin/env python3
"""One-shot detached HRES worker wrapper with exclusive exit/marker names."""
import json, subprocess, sys, time, traceback
from pathlib import Path
base=Path('/content/r237m1v2')
exit_path=base/'HRES_2022_exit_v1.json';done=base/'HRES_2022_done_v1'
if exit_path.exists() or done.exists():raise FileExistsError('Stage already finished')
t=time.time()
try:code=subprocess.run([sys.executable,'/content/hres_2022_v1.py'],check=False).returncode
except BaseException:traceback.print_exc();code=99
with exit_path.open('x') as f:json.dump({'source':'HRES_2022','exit_code':code,'started_epoch':t,'ended_epoch':time.time(),'elapsed_s':time.time()-t},f)
done.touch(exist_ok=False)
sys.exit(code)
