#!/usr/bin/env python3
"""Read-only checksum audit of previously staged PDFs; writes report to writable O:."""
import hashlib,json,sys
from pathlib import Path
entries=[json.loads(s) for s in open(sys.argv[1])]
out=Path(sys.argv[2]);out.parent.mkdir(parents=True,exist_ok=True)
with out.open('x') as f:
 for x in entries:
  try:
   p=Path(x['staged_path']);h=hashlib.sha256()
   with p.open('rb') as stream:
    for b in iter(lambda:stream.read(1048576),b''):h.update(b)
   status='ok' if p.stat().st_size==x['bytes'] and h.hexdigest()==x['sha256'] else 'mismatch'
  except (OSError,ValueError) as e:status='unreadable:'+str(e)
  f.write(json.dumps({'library':x['library'],'attachment':x['attachment'],'status':status})+'\n')
  if status!='ok':print(x['library'],x['attachment'],status,flush=True)
print('audited',len(entries),flush=True)
