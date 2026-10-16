#!/usr/bin/env python3
import requests, zipfile, pathlib, time
u='https://zenodo.org/api/records/20795548/files/SPIN_v1.0.1_output.zip/content'
p=pathlib.Path('/content/b2/SPIN_v1.0.1_output.zip')
r=requests.get(u,stream=True,timeout=120);r.raise_for_status()
with p.open('xb') as f:
 for chunk in r.iter_content(1024*1024):
  if chunk:f.write(chunk)
print('SPIN_BYTES',p.stat().st_size,flush=True)
with zipfile.ZipFile(p) as z:
 print('SPIN_ZIP',[(a.filename,a.file_size) for a in z.infolist()][:150],flush=True)
