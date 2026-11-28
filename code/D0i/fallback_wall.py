#!/usr/bin/env python3
"""One isolated retry only for a runtime-listed AD nut wall replacement."""
import gzip
import re
import shutil
import sys
from pathlib import Path
src, dst, log = map(Path, sys.argv[1:])
assert not dst.exists()
with gzip.open(log, 'rt', errors='replace') as f:
    text = f.read()
m = re.search(r'Unknown patchField type\s+(\S+).*?Valid patchField types\s*:\s*\d+\s*\((.*?)\)', text, re.S)
assert m, 'No explicit runtime list; no blind replacement'
old = m[1]
available = set(m[2].split())
assert old == 'nutUSpaldingWallFunctionDF' and 'nutUSpaldingWallFunction' in available, (old, 'not approved mapping')
shutil.copytree(src, dst, ignore=shutil.ignore_patterns('processor*', '*.log', 'postProcessing', '[1-9]*'))
p = dst/'0/nut'
s = p.read_text()
assert s.count(old) == 6, 'unexpected wall patch count'
p.write_text(s.replace(old, 'nutUSpaldingWallFunction'))
shutil.copy2(src/'checkMesh.log', dst/'checkMesh.log')
print(f'RETRY {old} -> nutUSpaldingWallFunction; new case {dst}', flush=True)
