#!/usr/bin/env python3
"""Read-only SHA-256 of candidate paths passed on stdin."""
import sys,json,hashlib
for line in sys.stdin:
    x=json.loads(line); h=hashlib.sha256()
    try:
        with open(x['path'],'rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        x['sha256']=h.hexdigest()
    except Exception as e:x['error']=str(e)
    print(json.dumps(x,ensure_ascii=False),flush=True)
