#!/usr/bin/env python3
import os,sys,subprocess,tarfile,hashlib,time,traceback
from pathlib import Path
try:
 p=Path('/content/input_bundle.tar.gz');assert hashlib.sha256(p.read_bytes()).hexdigest()=='c2d434658be5b0cae331df633cbc02dfe906bb906e7dbe074204a1a5e45998b6'
 with tarfile.open(p) as t:t.extractall('/content',filter='data')
 print('EXTRACTED',flush=True)
 subprocess.run(['uv','venv','/content/v4venv','--python','/usr/bin/python3.12'],check=True)
 subprocess.run(['uv','pip','install','--python','/content/v4venv/bin/python','climada==6.1.0','GDAL==3.8.4'],check=True)
 print('INSTALLED',flush=True)
 env=os.environ.copy();env['MPLBACKEND']='Agg';env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1'
 result=subprocess.run(['/content/v4venv/bin/python','-u','/content/run_v4.py'],env=env)
 code=result.returncode
except Exception:
 traceback.print_exc();code=1
Path('/content/v4_worker_r2.exit').write_text(str(code)+'\n')
print('WORKER_EXIT',code,flush=True)
