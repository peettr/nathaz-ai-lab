#!/usr/bin/env python3
"""Sequential new-root Colab controllers; stop on first failure."""
from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parent
for kind in ('BG_1H','BG_3H'):
 p=root/f'{kind}_v4_20261115_1050'/'controller.py'
 print('START',kind,p,flush=True)
 rc=subprocess.run([sys.executable,str(p)],stdin=subprocess.DEVNULL).returncode
 print('TERMINAL',kind,'controller returncode',rc,flush=True)
 if rc:sys.exit(rc)
print('BOTH_CONTROLLERS_FINISHED',flush=True)
