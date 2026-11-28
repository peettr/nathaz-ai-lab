#!/usr/bin/env python3
"""Prepare two immutable G1 case inputs from the D0 fixed-inlet template."""
from pathlib import Path
import shutil, re, hashlib
base=Path(__file__).resolve().parent
src=base.parent/'D0g/cases/medium'
assert src.is_dir()
for grade, dims in {'coarse':(100,60,42),'medium':(130,70,50)}.items():
    dst=base/'cases'/grade
    assert not dst.exists(), f'preserve existing {dst}'
    shutil.copytree(src,dst,ignore=shutil.ignore_patterns('polyMesh','processor*','__pycache__','*.pyc','checkMesh.log'))
    block=dst/'system/blockMeshDict'; s=block.read_text()
    assert s.count('(92 48 32)')==1
    block.write_text(s.replace('(92 48 32)',f'({dims[0]} {dims[1]} {dims[2]})'))
    # Rebuild the per-face fixedValue inlet AFTER the new mesh exists; do not
    # reuse D0g's 1536 face values on a different mesh.
    for field,uniform in {'U':'(10 0 0)','k':'0.5','omega':'5'}.items():
        path=dst/'0'/field; s=path.read_text()
        s,n=re.subn(r'\binlet\s*\{\s*type fixedValue;\s*value nonuniform List<(?:vector|scalar)>\s+\d+\s*\([^;]*\);\s*\}',f'inlet {{ type fixedValue; value uniform {uniform}; }}',s,count=1,flags=re.S)
        assert n==1, (field,n)
        path.write_text(s)
    # The later D0f/D0k/D0l repairs are applied to the local isolated copy.
    for path in (dst/'0').iterdir():
        if path.is_file():
            s=path.read_text().replace('"(sideNeg|sidePos|top)" {type symmetry;}','"(sideNeg|sidePos|top)" {type symmetryPlane;}')
            s=re.sub(r'\bbottom\s*\{', 'ground {',s)
            if path.name=='nut':s=s.replace('nutUSpaldingWallFunctionDF','nutUSpaldingWallFunction')
            path.write_text(s)
    p=dst/'constant/transportProperties';p.write_text(p.read_text()+'\nPr 0.71; Prt 0.85;\n')
    p=dst/'system/fvSchemes';s=p.read_text(); assert s.count('divSchemes {default none;')==1
    p.write_text(s.replace('divSchemes {default none;','divSchemes {default none; div(pc) bounded Gauss upwind;'))
    p=dst/'system/controlDict';s=p.read_text();assert s.count('endTime 50;')==1
    p.write_text(s.replace('endTime 50;','endTime 3000;').replace('writeFormat binary; writePrecision 6;','writeFormat ascii; writePrecision 12;'))
    p=dst/'adjoint_pilot.py';s=p.read_text(); assert s.count("'primalMinResTol':1e-20")==1
    p.write_text(s.replace("'primalMinResTol':1e-20","'primalMinResTol':1e-4"))
    print(grade,dims,'background',dims[0]*dims[1]*dims[2], 'inputs',len([x for x in dst.rglob('*') if x.is_file()]))
    for name in ['system/blockMeshDict','system/snappyHexMeshDict','system/fvSchemes','system/controlDict','0/U']:
        f=dst/name;print(name,hashlib.sha256(f.read_bytes()).hexdigest())
