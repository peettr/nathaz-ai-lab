"""Inspect real AIWP netCDF metadata via bounded HTTP range reads."""
import requests, h5py, fsspec, time
base='https://noaa-oar-mlwp-data.s3.amazonaws.com/'
key='PANG_v100_GFS/2023/0419/PANG_v100_GFS_2023041900_f000_f240_06.nc'
url=base+key
r=requests.get(url,headers={'Range':'bytes=0-16383'},timeout=30)
print('RANGE',r.status_code,r.headers.get('Content-Range'),len(r.content),r.content[:8],flush=True)
f=fsspec.open(url,'rb',block_size=128*1024,cache_type='bytes').open()
t=time.time()
with h5py.File(f,'r') as h:
 print('ROOT',list(h.keys()),'ATTR',list(h.attrs.items()),flush=True)
 def show(name,obj):
  if isinstance(obj,h5py.Dataset):
   print('DATA',name,obj.shape,obj.dtype,'chunks',obj.chunks,'compression',obj.compression,flush=True)
 h.visititems(show)
 import numpy as np
 print('COORD',h['latitude'][:3],h['longitude'][:3],h['level'][:],h['time'][:3],flush=True)
 for k in ['t','q','u','v','z','u10','v10','t2']:
  st=time.time()
  d=h[k]
  print('READ',k,float(d[(2,0,200,1000) if d.ndim==4 else (2,200,1000)]),'time',round(time.time()-st,2),flush=True)
print('SECONDS',time.time()-t,flush=True)
