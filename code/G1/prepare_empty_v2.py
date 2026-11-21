#!/usr/bin/env python3
"""Stage a fresh blockMesh-only empty-flow case from a G1 grade input."""
import re,shutil,sys
from pathlib import Path
src,dst=map(Path,sys.argv[1:3]);assert src.is_dir() and not dst.exists()
shutil.copytree(src,dst,ignore=shutil.ignore_patterns('polyMesh','processor*','0/C','sample_cells.json','*.log','g1_driver.py','*.jsonl'))
for f in (dst/'0').iterdir():
 if not f.is_file():continue
 s=f.read_text()
 for patch in ('xneg','xpos','yneg','ypos','roof'):
  s,n=re.subn(r'\b'+patch+r'\s*\{[^{}]*\}', '',s)
  assert n==1,(f,patch,n)
 f.write_text(s)
cd=dst/'system/controlDict';s=cd.read_text();assert 'functions {' in s
s=s[:s.index('functions {')]+'''functions
{
  atBuilding
  {
    type probes;
    libs ("libsampling.so");
    writeControl timeStep;
    writeInterval 100;
    fields (U k);
    probeLocations ((0 0 2) (0 0 4) (0 0 8) (0 0 16));
  }
}
'''
s=s.replace('application DASimpleFoam','application simpleFoam').replace('endTime 5000;','endTime 5000;')
cd.write_text(s)
# Mesh comes solely from blockMesh; no snappy, no building.
print(dst)
