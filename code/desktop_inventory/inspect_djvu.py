#!/usr/bin/env python3
"""Read-only DjVu magic/chunk and SHA-256 inventory."""
import json,sys,hashlib
for line in sys.stdin:
    x=json.loads(line)
    try:
        h=hashlib.sha256()
        with open(x['path'],'rb') as f:
            first=f.read(32);h.update(first)
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        x['sha256']=h.hexdigest()
        x['header']=first[:26].hex()
        if first[:4]==b'AT&T' and first[4:8]==b'FORM' and first[12:16]==b'DJVM' and first[16:20]==b'DIRM':
            x['pages']=int.from_bytes(first[25:27],'big')
        elif first[:4]==b'AT&T' and first[12:16]==b'DJVU':x['pages']=1
    except Exception as e:x['error']=str(e)
    print(json.dumps(x,ensure_ascii=False),flush=True)
