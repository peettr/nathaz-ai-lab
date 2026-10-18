import urllib.request,time,os
for name,u in [('RAFT.NA.v20231016.nc','https://zenodo.org/api/records/10392725/files/RAFT.NA.v20231016.nc/content'),('STORMV4.zip','https://ndownloader.figshare.com/files/36391536')]:
 t=time.time();p='/content/'+name
 if not os.path.exists(p):urllib.request.urlretrieve(u,p)
 print(name,os.stat(p).st_size,round(time.time()-t,1),flush=True)
import importlib.util
print('climada installed', bool(importlib.util.find_spec('climada')),flush=True)
