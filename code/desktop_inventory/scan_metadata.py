#!/usr/bin/env python3
"""Read-only filesystem listing, emits JSONL; runs under nice/ionice remotely."""
import os,sys,json
roots = ['./Literature','./Book'] if len(sys.argv)==1 else sys.argv[1:]
for root in roots:
    for d, dirs, files in os.walk(root):
        for f in files:
            if not f.lower().endswith(('.pdf','.pdg','.djvu')): continue
            p=os.path.join(d,f)
            try: s=os.stat(p)
            except OSError as e:
                print(json.dumps({'path':p,'error':str(e)},ensure_ascii=False));continue
            print(json.dumps({'path':p,'size':s.st_size,'ext':os.path.splitext(f)[1].lower()},ensure_ascii=False))
