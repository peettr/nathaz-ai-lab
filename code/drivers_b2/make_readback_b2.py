#!/usr/bin/env python3
"""Prepare B2-only independent readback; retain B1 artifact unchanged."""
from pathlib import Path
import hashlib
here=Path(__file__).resolve().parent
src=(here.parent/'drivers_b1'/'readback_gc37x_b1.py').read_text()
assert "inputs_N1N3N4_v1" in src and "_GFS_b1" in src
src=src.replace('inputs_N1N3N4_v1','inputs_N8N9N10_v1').replace('_GFS_b1','_GFS_b2')
src=src.replace("assert event in ('N1','N3','N4')", "assert event in ('N8','N9','N10')")
out=here/'readback_gc37x_b2.py'
if out.exists(): assert out.read_text()==src
else:out.write_text(src)
compile(src,str(out),'exec')
print(out,hashlib.sha256(out.read_bytes()).hexdigest())
