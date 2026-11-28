#!/usr/bin/env python3
"""Stage D0l under a new CRC root, preserving D0k unchanged."""
from pathlib import Path
import shutil, hashlib
src=Path('/groups/kareem/[用户]/L26_21_DAFOAM_20261114_d0k/cases/medium')
root=Path('/groups/kareem/[用户]/L26_21_DAFOAM_20261114_d0l')
assert src.is_dir() and not root.exists(), 'missing input or destination already exists'
case=root/'cases/medium'
case.mkdir(parents=True)
for d in ('0','constant','system'):
    shutil.copytree(src/d,case/d)
for f in ('adjoint_pilot.py','checkMesh.log'):
    shutil.copy2(src/f,case/f)
assert not list(case.glob('processor*'))
schemes=case/'system/fvSchemes'
s=schemes.read_text()
needle='divSchemes {default none;'
assert s.count(needle)==1 and 'div(pc)' not in s
schemes.write_text(s.replace(needle,needle+' div(pc) bounded Gauss upwind;'))
control=case/'system/controlDict'
s=control.read_text()
assert s.count('endTime 50;')==1
control.write_text(s.replace('endTime 50;','endTime 3000;'))
pilot=case/'adjoint_pilot.py'
s=pilot.read_text()
needle="'primalMinResTol':1e-20"
assert s.count(needle)==1
# Initial maximal residual in D0k was 1; 1e-4 yields four decades.
pilot.write_text(s.replace(needle,"'primalMinResTol':1e-4"))
for p in (schemes,control,pilot):
    print(p,hashlib.sha256(p.read_bytes()).hexdigest())
print('STAGED',root,'NO_PROCESSORS',len(list(case.glob('processor*'))))
