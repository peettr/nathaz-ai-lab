#!/usr/bin/env python3
"""Run sealed controller from Linux spool; stdout remains on Linux side."""
from pathlib import Path
import os, subprocess, sys
r=Path(__file__).resolve().parent
archive=Path('./24_Urban_Wind_LBM/06_Logs/R21.4a_T17_periodic_ABL')/r.name
with (r/'allocation_events.log').open('x',buffering=1) as log:
 p=subprocess.run([sys.executable,str(r/'controller_hardened.py'),'--authorized-run'],cwd=r,env={**os.environ,'T17_ARCHIVE_ROOT':str(archive)},stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
print('CONTROLLER_EXIT',p.returncode,'LINUX_LOG',r/'allocation_events.log',flush=True)
sys.exit(p.returncode)
