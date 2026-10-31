"""Training-date AIWP HDF5 range probe; metadata and one station sample."""
import fsspec,h5py,time
url='https://noaa-oar-mlwp-data.s3.amazonaws.com/GRAP_v100_GFS/2022/0101/GRAP_v100_GFS_2022010100_f000_f240_06.nc'
t=time.monotonic()
with fsspec.open(url,'rb',block_size=262144,cache_type='readahead') as f:
 with h5py.File(f,'r') as h:
  print('ATTRS',list(h.attrs.items())[:12],flush=True)
  for name in h:
   x=h[name];print('FIELD',name,getattr(x,'shape',None),getattr(x,'chunks',None),flush=True)
  print('GRID',h['latitude'][:3],h['longitude'][:3],flush=True)
  for var in ('u10','v10'):
   for index in (0,1,2,3):
    print('SAMPLE',var,index,float(h[var][index,218,1049]),'elapsed',time.monotonic()-t,flush=True)
  print('ELAPSED',time.monotonic()-t,flush=True)
