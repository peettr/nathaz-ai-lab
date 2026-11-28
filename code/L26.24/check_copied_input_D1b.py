#!/usr/bin/env python3
"""Compare copied D1 serial S2 inputs byte-for-byte; write only D1b manifest."""
import hashlib,json
from pathlib import Path
old=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_D1/case')
new=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_D1b/case')
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''): h.update(block)
    return h.hexdigest()
rows=[]
for section in ('0','constant','system','44'):
    for src in sorted((old/section).rglob('*')):
        if not src.is_file(): continue
        rel=src.relative_to(old);dst=new/rel
        rows.append({'path':str(rel),'sha256':digest(src),'copied_sha256':digest(dst) if dst.is_file() else None})
assert rows
bad=[r['path'] for r in rows if r['sha256']!=r['copied_sha256']]
out=new.parent/'copied_input_sha256_D1b.json'
assert not out.exists()
out.write_text(json.dumps({'source':str(old),'copied':str(new),'count':len(rows),'bad':bad,'files':rows},indent=2)+'\n')
print('FILES',len(rows),'MISMATCHES',len(bad),flush=True)
if bad: raise SystemExit(1)
