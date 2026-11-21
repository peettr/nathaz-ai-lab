#!/usr/bin/env python3
"""Stage immutable S2 restart inputs in the fresh D1 root; no solver run."""
from pathlib import Path
import hashlib, json, shutil, sys
SRC=Path('/groups/kareem/[用户]/petw_runs/ubwp/r25_2_chew/S2_coarse/production/case')
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_D1')
MAN=Path(sys.argv[1])
assert ROOT.is_dir() and not (ROOT/'case').exists(), 'fresh unstaged case required'
assert len(list(SRC.glob('processor*/44'))) == 48
# Freeze the source configuration against the R25.2 handoff before any edits.
expected={}
for line in MAN.read_text().splitlines():
    import re
    m=re.match(r'^([0-9a-f]{64})  ((?:0|constant|system)/\S+)$',line)
    if m: expected[m.group(2)]=m.group(1)
assert len(expected) >= 30, len(expected)
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()
source_bad=[p for p,h in expected.items() if not (SRC/p).is_file() or digest(SRC/p)!=h]
assert not source_bad, ('S2 source differs from frozen handoff',source_bad)
case=ROOT/'case'
for folder in ('0','constant','system'):
    shutil.copytree(SRC/folder,case/folder)
for rank in range(48):
    proc=SRC/f'processor{rank}'
    dest=case/proc.name
    dest.mkdir()
    shutil.copytree(proc/'constant'/'polyMesh',dest/'constant'/'polyMesh')
    shutil.copytree(proc/'44',dest/'44')
assert all(digest(case/p)==h for p,h in expected.items()), 'copy hash mismatch'
(ROOT/'s2_sha256_compare.json').write_text(json.dumps({'source':str(SRC),'checkpoint':'44','manifest':str(MAN),'file_count':len(expected),'mismatches':source_bad,'all_copied_match':True,'source_0_U_sha256':expected['0/U'],'TInF_seed':'wall-clock seed; not fixed across continuation'},indent=2)+'\n')
print('S2_SHA256_MATCH',len(expected),flush=True)
