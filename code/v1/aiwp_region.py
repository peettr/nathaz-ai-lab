"""Second bounded read: 2024 Milton landing vicinity msl/u10/v10/u850/v850."""
import io,time,requests,h5py,json,collections,numpy as np
URL='https://noaa-oar-mlwp-data.s3.amazonaws.com/FOUR_v200_GFS/2024/1009/FOUR_v200_GFS_2024100900_f000_f240_06.nc';SIZE=7472991383
class Range(io.RawIOBase):
 def __init__(self):self.pos=0;self.n=0;self.calls=0;self.cache=collections.OrderedDict();self.t0=time.monotonic();self.s=requests.Session()
 def readable(self):return True
 def seekable(self):return True
 def tell(self):return self.pos
 def seek(self,o,w=0):self.pos=o if w==0 else self.pos+o if w==1 else SIZE+o;return self.pos
 def read(self,n=-1):
  if n<0:n=SIZE-self.pos
  out=[]
  while n>0 and self.pos<SIZE:
   k=self.pos//262144;ofs=self.pos%262144
   if k not in self.cache:
    if self.n>=150_000_000 or self.calls>=500 or time.monotonic()-self.t0>180:raise RuntimeError('STOP limit')
    a=k*262144;r=self.s.get(URL,headers={'Range':f'bytes={a}-{min(SIZE-1,a+262143)}'},timeout=30)
    if r.status_code!=206:raise RuntimeError('Range denied '+str(r.status_code))
    self.cache[k]=r.content;self.n+=len(r.content);self.calls+=1
    if len(self.cache)>256:self.cache.popitem(last=False)
   else:self.cache.move_to_end(k)
   b=self.cache[k];m=min(n,len(b)-ofs);out.append(b[ofs:ofs+m]);self.pos+=m;n-=m
  return b''.join(out)
 def readinto(self,b):d=self.read(len(b));b[:len(d)]=d;return len(d)
r=Range();out={}
try:
 with h5py.File(r,'r') as h:
  lat=h['latitude'][:];lon=h['longitude'][:];lev=h['level'][:];tm=h['time'][:]
  print('coords',lat[0],lat[-1],lon[0],lon[-1],lev.tolist(),tm[0],tm[4],flush=True)
  if lon.max()>180:where_lon=((lon+180)%360)-180
  else:where_lon=lon
  ys=np.where((lat>=24)&(lat<=32))[0];xs=np.where((where_lon>=-87)&(where_lon<=-78))[0]
  sl=(slice(ys.min(),ys.max()+1),slice(xs.min(),xs.max()+1));zi=int(np.argmin(abs(lev-850)))
  out['coordinates']={'lat':lat[sl[0]].tolist(),'lon':where_lon[sl[1]].tolist(),'level_850_index':zi,'level_850_value':int(lev[zi]),'time_values':tm[:9].tolist()}
  out['fields']={}
  for var in ('msl','u10','v10','u','v'):
   d=h[var][4,zi,*sl] if var in ('u','v') else h[var][4,*sl]
   out['fields'][var]={'shape':d.shape,'min':float(np.min(d)),'max':float(np.max(d))}
   np.save('/content/aiwp_'+var+'_slice.npy',d)
  u=np.load('/content/aiwp_u_slice.npy');v=np.load('/content/aiwp_v_slice.npy')
  dy=float(abs(lat[1]-lat[0]))*111_200;dx=float(abs(lon[1]-lon[0]))*111_200*np.cos(np.deg2rad(lat[sl[0]].mean()))
  vort=np.gradient(v,dx,axis=1)-np.gradient(u,dy,axis=0)*(1 if lat[1]>lat[0] else -1)
  out['vorticity_850']={'min':float(vort.min()),'max':float(vort.max()),'units':'s^-1','method':'central finite difference'}
  pp=np.load('/content/aiwp_msl_slice.npy');j,i=np.unravel_index(np.argmin(pp),pp.shape)
  out['region_min_msl']={'lat':float(lat[ys[j]]),'lon':float(where_lon[xs[i]]),'pa':float(pp[j,i])}
except Exception as ex:out['error']=repr(ex);print('ERROR',repr(ex),flush=True)
out['metrics']={'bytes':r.n,'requests':r.calls,'elapsed_s':round(time.monotonic()-r.t0,2),'file_size':SIZE};print('FINAL',json.dumps({k:v for k,v in out.items() if k!='coordinates'}),flush=True)
with open('/content/aiwp_region_metrics.json','x') as f:json.dump({k:v for k,v in out.items() if k!='coordinates'},f,indent=2)
