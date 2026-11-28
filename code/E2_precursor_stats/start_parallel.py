import os,subprocess
os.kill(786,15)
p='/content/e2/parallel.py'
open(p,'w').write('''import requests,concurrent.futures,os,time,hashlib,zipfile,json
url='https://zenodo.org/api/records/19041698/files/boundaryData.zip/content';size=3203620880; block=16*1024*1024
path='/content/e2/parallel.zip';fd=os.open(path,os.O_CREAT|os.O_RDWR,0o600);os.ftruncate(fd,size)
def get(i):
 lo=i*block;hi=min(size,lo+block)-1
 for a in range(3):
  try:
   r=requests.get(url,headers={'Range':f'bytes={lo}-{hi}'},timeout=(20,80))
   if r.status_code!=206 or len(r.content)!=hi-lo+1: raise ValueError((r.status_code,len(r.content),lo,hi))
   os.pwrite(fd,r.content,lo);return i
  except Exception:
   if a==2:raise
   time.sleep(a+1)
t=time.time();n=(size+block-1)//block
with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
 for j,i in enumerate(pool.map(get,range(n))):
  if (j+1)%12==0:print('PROGRESS',j+1,n,'elapsed',round(time.time()-t),flush=True)
os.close(fd)
h=hashlib.md5()
with open(path,'rb') as f:
 for chunk in iter(lambda:f.read(8388608),b''):h.update(chunk)
with zipfile.ZipFile(path) as z:
 files=[x for x in z.namelist() if x.endswith('/U')];times=sorted(float(x.split('/')[1]) for x in files)
 meta=dict(size=size,md5=h.hexdigest(),elapsed=time.time()-t,frames=len(files),first=times[:3],last=times[-3:])
open('/content/e2/download_meta.json','w').write(json.dumps(meta));print('DONE',meta,flush=True)
''')
f=open('/content/e2/parallel.log','w');q=subprocess.Popen(['python',p],stdout=f,stderr=subprocess.STDOUT,start_new_session=True);print('PID',q.pid)
