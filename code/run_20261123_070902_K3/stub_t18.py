#!/usr/bin/python3.10
"""Fixture only: real worker, synthetic solver, never physics evidence."""
from pathlib import Path
import os
if os.environ.get('T17_B_MODE')=='compilecheck':
 d=Path(os.environ['T17_B_DIR']);d.mkdir(exist_ok=True);(d/'producer.done').write_text('10\n');print('FIXTURE ONLY OpenCL C code successfully compiled')
elif os.environ.get('T17_B_MODE')=='smoke':
 d=Path(os.environ['T17_B_DIR'])
 d.mkdir(exist_ok=True)
 (d/'rho_monitor.csv').write_text(''.join(f'{s},1.0,1.0\n' for s in list(range(1000,53001,1000))+[53851]))
 (d/'producer.done').write_text('53851\n')
 print('SYNTHETIC_C0_STUB_ONLY')
else:
 from runpy import run_path
 run_path(str(Path(__file__).with_name('stub_native_original.py')),run_name='__main__')
