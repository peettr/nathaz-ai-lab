#!/usr/bin/env python3
"""Exclusive Colab detached M2 AI retrieval; terminal marker carries exit code."""
import os,subprocess,sys
from pathlib import Path
r=Path('/content/r237_m2');assert r.is_dir()
assert not (r/'ai_2023_v1.launch').exists()
(r/'ai_2023_v1.launch').open('x').write('one launch\n')
cmd=['/bin/bash','-c',"python3 -u /content/r237_m2/ai_2023_v1.py GRAP_v100_IFS && python3 -u /content/r237_m2/ai_2023_v1.py PANG_v100_IFS; status=$?; printf '%s\\n' \"$status\" > /content/r237_m2/ai_2023_v1.exit; touch /content/r237_m2/ai_2023_v1.done; exit \"$status\""]
with (r/'ai_2023_v1.log').open('x') as f:
    p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('DETACHED_PID',p.pid,flush=True)
