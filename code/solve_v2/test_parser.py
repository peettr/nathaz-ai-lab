#!/usr/bin/env python3
"""Purely synthetic parser fixture; not scientific measurements."""
from pathlib import Path
import subprocess, tempfile, json
here=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(dir=here) as td:
 root=Path(td);p=root/'postProcessing/atBuilding/0';p.mkdir(parents=True)
 (p/'U').write_text('# Probe 0\n100 (9 0 0) (10 0 0) (11 0 0) (12 0 0)\n')
 (p/'k').write_text('# Probe 0\n100 0.1 0.1 0.1 0.1\n')
 target=root/'empty_reference.json'
 subprocess.run(['python3',str(here.parent/'parse_empty_v2.py'),str(root),str(target)],check=True,capture_output=True)
 data=json.loads(target.read_text())
 assert data['U_at_H']==11 and len(data['rows'])==4
print('synthetic empty parser PASS')
