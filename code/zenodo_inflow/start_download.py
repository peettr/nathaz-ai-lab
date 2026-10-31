import os, subprocess, textwrap
os.makedirs('/content/zenodo19041698',exist_ok=True)
p='/content/zenodo19041698/download.py'
open(p,'w').write('''import requests,time,os,hashlib,json,zipfile
u="https://zenodo.org/api/records/19041698/files/boundaryData.zip/content"
p="/content/zenodo19041698/boundaryData.zip"
t=time.time();h=hashlib.md5();n=0
with requests.get(u,stream=True,timeout=(30,120)) as r:
 r.raise_for_status()
 with open(p,"wb") as f:
  for chunk in r.iter_content(4*1024*1024):
   if chunk:
    f.write(chunk);h.update(chunk);n+=len(chunk)
    if n//(256*1024*1024)!=(n-len(chunk))//(256*1024*1024):print("DOWNLOAD",n,"seconds",int(time.time()-t),flush=True)
print("MD5",h.hexdigest(),"BYTES",n,"SECONDS",time.time()-t,flush=True)
with zipfile.ZipFile(p) as z:
 a=[dict(name=x.filename,size=x.file_size,compressed=x.compress_size) for x in z.infolist()]
 open('/content/zenodo19041698/zip_listing.json','w').write(json.dumps(a,indent=2))
 print('ENTRIES',len(a),'UNCOMPRESSED',sum(x['size'] for x in a),flush=True)
open('/content/zenodo19041698/download.done','w').write(json.dumps(dict(bytes=n,md5=h.hexdigest(),elapsed_s=time.time()-t)))
''')
print('DISK',subprocess.run(['df','-h','/content'],capture_output=True,text=True).stdout)
f=open('/content/zenodo19041698/download.log','w')
proc=subprocess.Popen(['python',p],stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
print('PID',proc.pid,flush=True)
