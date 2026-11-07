#!/usr/bin/env python3
"""Stage four disjoint T03 v1.2 cases on CRC login node; no solver execution."""
from pathlib import Path
import argparse, json, re, shutil
SRC=Path('/groups/kareem/[用户]/L22_6/L22_6_T03_v11_20261021_03/B0')
ROOT=Path('/users/[用户]')
p=argparse.ArgumentParser();p.add_argument('tag',choices=('B0','B0prime','B1','REF'));a=p.parse_args()
case=ROOT/f'L22_6_T03_v12_{a.tag}_20261021_01'
assert not case.exists(),f'refuse to overwrite {case}'
for folder in ('0','system','constant/boundaryData/inlet'):
    (case/folder).mkdir(parents=True,exist_ok=True)
for folder in ('0','system','constant'):
    for f in (SRC/folder).iterdir():
        if f.is_file():shutil.copy2(f,case/folder/f.name)
for f in (SRC/'constant/boundaryData/inlet').iterdir():
    if f.is_file(): shutil.copy2(f,case/'constant/boundaryData/inlet'/f.name)
control=case/'system/controlDict'; t=control.read_text(); t,n=re.subn(r'(?m)^(\s*endTime\s+)40\s*;',r'\g<1>120;',t); assert n==1,n
t,n=re.subn(r'(?m)^(\s*writeInterval\s+)40\s*;',r'\g<1>120;',t);assert n==1,n
if a.tag=='REF':
    t=t.replace('libturbulentInflow.so','libT03PrivateRef.so')
control.write_text(t)
if a.tag in ('B1','REF'):
    inp=case/'constant/boundaryData/inlet'; srcpsi=Path('/groups/kareem/[用户]/L22_6/L22_6_T03_v11_20261021_03/B1/constant/boundaryData/inlet/psi')
    shutil.copy2(srcpsi,inp/'psi')
else:
    psi=case/'constant/boundaryData/inlet/psi'
    if psi.exists():psi.unlink()
if a.tag=='REF':
    u=case/'0/U'; t=u.read_text(); t,n=re.subn(r'(?m)(\s*type\s+)turbulentDFMInlet(\s*;)',r'\1turbulentDFMVeerInlet\2',t,count=1);assert n==1,n;u.write_text(t)
(case/'stage.json').write_text(json.dumps({'tag':a.tag,'source':str(SRC),'analysis_window_s':[5,120],'probes':50,'seed_policy':'TInF original rndGen_ initialized from time(NULL), record solver startup epoch; no user seed parameter'},indent=2)+'\n')
print(case)
