import os
for p in ['/content/e2/parallel.log','/content/e2/download_meta.json']:
 print(p,os.path.getsize(p) if os.path.exists(p) else None)
 if p.endswith('.log') and os.path.exists(p):print(open(p).read()[-1500:])
