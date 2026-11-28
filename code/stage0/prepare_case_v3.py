#!/usr/bin/env python3
"""Stage a NEW CRC-only T03 v3 case from existing v2 result WITHOUT its results.
File operations only. Never run this on 工作站; never overwrite an existing case.
"""
import argparse,re,shutil
from pathlib import Path
Z=(.1,.3,.5,.9,1.5)
NUM=r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('source',type=Path);ap.add_argument('dest',type=Path)
    ap.add_argument('--bc',choices=('B0','Veer'),required=True)
    ap.add_argument('--psi-top',type=float,default=20.)
    a=ap.parse_args()
    if a.dest.exists(): raise FileExistsError(a.dest)
    a.dest.mkdir(parents=True)
    for sub in ('0','system'):
        shutil.copytree(a.source/sub,a.dest/sub,ignore=shutil.ignore_patterns('postProcessing','polyMesh'))
    (a.dest/'constant').mkdir()
    for f in (a.source/'constant').iterdir():
        if f.name in ('polyMesh','dynamicMeshDict'): continue
        if f.is_dir(): shutil.copytree(f,a.dest/'constant'/f.name)
        elif f.is_file(): shutil.copy2(f,a.dest/'constant'/f.name)
    control=a.dest/'system/controlDict'; text=control.read_text()
    # Ensure the probe list of five 36-probe rows spans y=-.875...+.875 at Δy=.05.
    pts='\n'.join(f'            (-2.1 {-0.875 + j*.05:.3f} {z:.3f})' for z in Z for j in range(36))
    pat=r'(\bprobeLocations\s*\()(.*?)(\)\s*;)'
    text,n=re.subn(pat,lambda m:m.group(1)+'\n'+pts+'\n        '+m.group(3),text,flags=re.S)
    if n!=1: raise ValueError(f'expected exactly one probeLocations list, found {n}')
    if a.bc=='Veer':
        text,n=re.subn('libturbulentInflow\\.so','libturbulentDFMVeerInlet.so',text)
        if n<1: raise ValueError('missing original library in controlDict')
    control.write_text(text)
    if a.bc=='Veer':
        u=a.dest/'0/U'; t=u.read_text();t,n=re.subn(r'(\btype\s+)turbulentDFMInlet(\s*;)',r'\1turbulentDFMVeerInlet\2',t,count=1)
        if n!=1: raise ValueError('expected original inlet BC in 0/U')
        u.write_text(t)
    bd=a.dest/'constant/boundaryData/inlet'
    points=[list(map(float,re.findall(NUM,s))) for s in (bd/'points').read_text().splitlines() if s.lstrip().startswith('(') and len(re.findall(NUM,s))==3]
    if len(points)!=164: raise ValueError(f'expected 164 target points, got {len(points)}')
    vals=[min(max(a.psi_top*z/1.8,0.),a.psi_top) for _,_,z in points]
    # BoundaryData OpenFOAM raw scalar list, no FoamFile header.
    psi=bd/'psi'; psi.write_text('164\n(\n'+'\n'.join(f'{v:.10f}' for v in vals)+'\n)\n')
    print(f'staged new case {a.dest}; {len(Z)*36} probes; psi top={a.psi_top}')
if __name__=='__main__':main()
