#!/usr/bin/env python3
"""Run on CRC login node: stage an isolated minimal E7 inlet case, never edit E7."""
from pathlib import Path
import shutil,re,json,hashlib
SRC=Path('/groups/kareem/[用户]/petw_runs/cfd/weuq_e7_tinf_20261018T0750Z_v2/case')
ROOT=Path('/groups/kareem/[用户]/L22_6/L22_6_T03_v11_20261021_01')
assert not ROOT.exists(), 'Refuse to overwrite existing run root'
for tag in ('B0','B1'):
    case=ROOT/tag
    for sub in ('0','system','constant/boundaryData/inlet'):
        (case/sub).mkdir(parents=True,exist_ok=True)
    for f in (SRC/'0').iterdir():
        if f.is_file(): shutil.copy2(f,case/'0'/f.name)
    for f in (SRC/'system').iterdir():
        if f.is_file() and f.name not in ('snappyHexMeshDict',): shutil.copy2(f,case/'system'/f.name)
    for f in (SRC/'constant').iterdir():
        if f.is_file(): shutil.copy2(f,case/'constant'/f.name)
    for f in (SRC/'constant/boundaryData/inlet').iterdir():
        if f.is_file(): shutil.copy2(f,case/'constant/boundaryData/inlet'/f.name)
    p=case/'system/blockMeshDict'; txt=p.read_text().replace('xMax\t\t3.1000;', 'xMax\t\t-1.7000;').replace('xCells\t\t52;', 'xCells\t\t4;'); p.write_text(txt)
    p=case/'system/decomposeParDict'; txt=p.read_text().replace('numberOfSubdomains\t48;', 'numberOfSubdomains\t8;'); p.write_text(txt)
    p=case/'system/controlDict'; txt=p.read_text(); txt=re.sub(r'endTime\s+12;', 'endTime 40;',txt); txt=txt.replace('writeInterval 12;', 'writeInterval 40;').replace('adjustTimeStep \t\tyes;', 'adjustTimeStep no;').replace('maxDeltaT \t0.005000;', 'maxDeltaT 0.005000;')
    txt=txt[:txt.index('functions\n{')]+'''functions
{
    InletPatch
    {
        type patchProbes;
        libs ("libsampling.so");
        patchName inlet;
        writeControl timeStep;
        writeInterval 1;
        timeStart 0;
        fields (U);
        probeLocations
        (
''' + ''.join(f'            (-2.1 {y:.3f} {z:.3f})\n' for z in (.1,.3,.5, .9,1.5) for y in (-.9,-.7,-.5,-.3,-.1,.1,.3,.5,.7,.9)) + '''        );
    }
}
// ************************************************************************* //
'''
    p.write_text(txt)
    # original inlet expects scalar U; B1 retains same U/R/L and stores psi for ignored-input control
    if tag=='B1':
        inp=case/'constant/boundaryData/inlet'; points=(inp/'points').read_text(); zz=[float(x) for x in re.findall(r'\(\s*-2\.100000e\+00\s+0\.000000e\+00\s+([0-9.eE+-]+)\s*\)',points)]
        assert len(zz)==164,len(zz)
        (inp/'psi').write_text(f'{len(zz)}\n(\n'+''.join(f'{min(20.,max(0.,20*z/1.8)):.10f}\n' for z in zz)+')\n')
manifest={'source':str(SRC),'root':str(ROOT),'mesh_cells':[4,44,36],'inlet_probes':50,'sampling_dt':.005,'end_time':40,'run_tags':['B0','B1'],'notes':'Assumptions: 40s including first 5s transient; 0.2m y probe spacing; five z levels. B1 original BC ignores psi.'}
(ROOT/'stage.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest))
