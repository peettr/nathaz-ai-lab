#!/usr/bin/env python3
"""On desktop, verify transferred regular files and place without overwrites."""
import hashlib,json,sys
from pathlib import Path
if len(sys.argv)!=2 or not sys.argv[1].startswith('batch_'):raise SystemExit('batch tag required')
tag=sys.argv[1];base=Path.home()/'ftkb_figures/p14_pdfs';entries=[json.loads(x) for x in (base/'manifests'/f'{tag}.jsonl').read_text().splitlines()]
for x in entries:
    source=base/'staging'/tag/x['original_path'].lstrip('/')
    dest=Path(x['staged_path'])
    target=dest if dest.exists() else source
    if not target.is_file():raise FileNotFoundError(target)
    h=hashlib.sha256()
    with target.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    if target.stat().st_size!=x['bytes'] or h.hexdigest()!=x['sha256']:raise ValueError('SHA256/length mismatch: '+str(target))
    if not dest.exists():
        dest.parent.mkdir(parents=True,exist_ok=True);source.rename(dest)
    print('verified',x['library'],x['attachment'],flush=True)
print('batch',tag,'all verified',len(entries),flush=True)
