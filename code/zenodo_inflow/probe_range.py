import requests,time
for u in ['https://zenodo.org/api/records/19041698/files/boundaryData.zip/content','https://zenodo.org/records/19041698/files/boundaryData.zip?download=1']:
 t=time.time()
 try:
  r=requests.get(u,headers={'Range':'bytes=0-1023'},timeout=25,stream=True)
  print(r.status_code,r.headers.get('Content-Length'),r.headers.get('Content-Range'),r.url,'time',round(time.time()-t,2))
  print('got',len(next(r.iter_content(2048))))
 except Exception as e:print(type(e).__name__,str(e)[:300])
