import os,subprocess
os.kill(9847,15)
root='/content/zenodo19041698/attempt3';os.makedirs(root,exist_ok=True)
p=root+'/parallel.py'
open(p,'w').write('''import os,requests,time,concurrent.futures,hashlib,zipfile,json
url='https://zenodo.org/api/records/19041698/files/boundaryData.zip/content';size=3203620880;block=16*1024*1024
path='/content/zenodo19041698/attempt3/boundaryData.zip'; fd=os.open(path,os.O_CREAT|os.O_RDWR,0o600);os.ftruncate(fd,size)
def fetch(i):
 start=i*block;end=min(size,start+block)-1
 for attempt in range(4):
  try:
   r=requests.get(url,headers={'Range':f'bytes={start}-{end}'},timeout=(20,90))
   if r.status_code!=206 or len(r.content)!=end-start+1:raise ValueError((r.status_code,len(r.content),start,end))
   os.pwrite(fd,r.content,start);return i,len(r.content)
  except Exception as e:
   if attempt==3:raise
   time.sleep(attempt+1)
t=time.time();total=0
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
 futures=[pool.submit(fetch,i) for i in range((size+block-1)//block)]
 for j,f in enumerate(concurrent.futures.as_completed(futures)):
  i,n=f.result();total+=n
  if (j+1)%12==0:print('PROGRESS',j+1,len(futures),total,'seconds',round(time.time()-t),flush=True)
os.close(fd)
h=hashlib.md5()
with open(path,'rb') as f:
 for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
print('MD5',h.hexdigest(),'SECONDS',time.time()-t,flush=True)
with zipfile.ZipFile(path) as z:
 a=[dict(name=x.filename,size=x.file_size,compressed=x.compress_size) for x in z.infolist()]
 open('/content/zenodo19041698/attempt3/zip_listing.json','w').write(json.dumps(a,indent=2))
 print('ENTRIES',len(a),'UNCOMPRESSED',sum(x['size'] for x in a),flush=True)
open('/content/zenodo19041698/attempt3/download.done','w').write(json.dumps(dict(bytes=total,md5=h.hexdigest(),elapsed_s=time.time()-t)))
''')
f=open(root+'/download.log','w');q=subprocess.Popen(['python',p],stdout=f,stderr=subprocess.STDOUT,start_new_session=True);print('PID',q.pid)
