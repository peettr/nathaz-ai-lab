import os,subprocess,time
os.makedirs('/content/e2',exist_ok=True)
s='''import requests,hashlib,time,os,zipfile,json
u="https://zenodo.org/api/records/19041698/files/boundaryData.zip/content"
p="/content/e2/boundaryData.zip"
h=hashlib.md5(); n=0; start=time.time()
with requests.get(u,stream=True,timeout=(20,120)) as r:
 r.raise_for_status()
 with open(p,'wb') as f:
  for chunk in r.iter_content(4*1024*1024):
   if chunk:
    f.write(chunk); h.update(chunk);n+=len(chunk)
    if n//268435456!=(n-len(chunk))//268435456: print(n,round(time.time()-start),flush=True)
with zipfile.ZipFile(p) as z:
 names=z.namelist(); times=sorted(float(x.split('/')[1]) for x in names if x.endswith('/U'))
 fields=sorted(set(x.split('/')[-1] for x in names if x.startswith('boundaryData/') and x.count('/')==2))
 meta=dict(bytes=n,md5=h.hexdigest(),elapsed_s=time.time()-start,entries=len(names),frames=len(times),first=times[:5],last=times[-5:],fields=fields)
open('/content/e2/download_meta.json','w').write(json.dumps(meta))
print(meta,flush=True)
'''
open('/content/e2/download.py','w').write(s)
f=open('/content/e2/download.log','w')
p=subprocess.Popen(['python','/content/e2/download.py'],stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('PID',p.pid)
