#!/usr/bin/env python3
"""Create a no-building ABL companion from a frozen G1 case.

Run only after mesh generation: inlet nonuniform values must be rebuilt for
this new blockMesh. This utility never edits the source case.
"""
import re
import shutil
import sys
from pathlib import Path
src=Path(sys.argv[1]);dst=Path(sys.argv[2]);assert src.is_dir() and not dst.exists()
shutil.copytree(src,dst,ignore=shutil.ignore_patterns('polyMesh','processor*','postProcessing','0/C','*.log','sample_cells.json'))
# blockMesh has no building; retain the exact domain, vertical grading and top patch.
for f in (dst/'0').iterdir():
    if not f.is_file():continue
    s=f.read_text()
    for patch in ('xneg','xpos','yneg','ypos','roof'):
        s,n=re.subn(r'\b'+patch+r'\s*\{[^{}]*\}', '',s)
        assert n==1,(f,patch,n)
    for name in ('U','k','omega'):
        if f.name==name:
            s,n=re.subn(r'\binlet\s*\{[^{}]*\}',f'inlet {{type fixedValue; value uniform {"(10 0 0)" if name=="U" else "1"};}}',s)
            assert n==1
    f.write_text(s)
# Rebuild an inlet list after blockMesh; top values already match the original.
print(dst)
