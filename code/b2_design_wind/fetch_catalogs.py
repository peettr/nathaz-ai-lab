#!/usr/bin/env python3
"""Stage only RAFT track and STORM v4 archive on owned Colab VM."""
import hashlib, pathlib, requests, zipfile, time
root=pathlib.Path('/content/b2'); root.mkdir(exist_ok=True)
urls={'RAFT.NA.v20231016.nc':'https://zenodo.org/api/records/10392725/files/RAFT.NA.v20231016.nc/content','STORMV4.zip':'https://ndownloader.figshare.com/files/36391536','STORM_README.txt':'https://ndownloader.figshare.com/files/24876980'}
for name,url in urls.items():
 p=root/name
 if p.exists(): print('already exists',name,p.stat().st_size,flush=True);continue
 t=time.time();h=hashlib.sha256()
 with requests.get(url,stream=True,timeout=120) as r:
  r.raise_for_status()
  with p.open('xb') as f:
   for chunk in r.iter_content(1024*1024):
    if chunk:f.write(chunk);h.update(chunk)
 print(name,p.stat().st_size,h.hexdigest(),round(time.time()-t,1),flush=True)
with zipfile.ZipFile(root/'STORMV4.zip') as z:
 for i in z.infolist():print('ZIP',i.filename,i.file_size,flush=True)
print('DONE_FETCH',flush=True)
