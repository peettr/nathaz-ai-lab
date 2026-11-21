#!/usr/bin/env python3
"""Prepare exactly one isolated retry for unsupported AD nut wall type."""
import re
import shutil
import sys
from pathlib import Path
src, dst, *logs = map(Path, sys.argv[1:])
assert not dst.exists()
text = '\n'.join(x.read_text(errors='replace') for x in logs if x.exists())
m = re.search(r'Unknown patchField type\s+(\S+).*?Valid patchField types\s*:\s*\d+\s*\((.*?)\)',text,re.S)
assert m, 'No explicit runtime list; no blind replacement'
old = m[1]; available = set(m[2].split())
assert old == 'nutUSpaldingWallFunctionDF', f'unsupported type {old} not safely mapped'
new = 'nutUSpaldingWallFunction'
assert new in available, f'{new} not listed by runtime'
shutil.copytree(src,dst,ignore=shutil.ignore_patterns('processor*','checkMesh.log','*.log'))
path = dst/'0/nut'
s = path.read_text()
assert s.count(old) == 6, 'unexpected wall patch count'
path.write_text(s.replace(old,new))
shutil.copy2(src/'checkMesh.log',dst/'checkMesh.log')
print(f'RETRY {old} -> {new}; ground smooth-wall assumption; source={src} destination={dst}')
