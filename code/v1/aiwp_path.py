"""One initialized FOUR v200 Milton path from bounded remote MSLP patches."""
import io,time,requests,h5py,json,collections,numpy as np
URL='https://noaa-oar-mlwp-data.s3.amazonaws.com/FOUR_v200_GFS/2024/1009/FOUR_v200_GFS_2024100900_f000_f240_06.nc';SIZE=7472991383
class RR(io.RawIOBase):
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
    if self.n>=450_000_000 or self.calls>=1800 or time.monotonic()-self.t0>250:raise RuntimeError('bounded cap')
    a=k*262144;r=self.s.get(URL,headers={'Range':f'bytes={a}-{min(SIZE-1,a+262143)}'},timeout=30)
    if r.status_code!=206:raise RuntimeError('Range denied '+str(r.status_code))
    self.cache[k]=r.content;self.n+=len(r.content);self.calls+=1
    if len(self.cache)>128:self.cache.popitem(last=False)
   else:self.cache.move_to_end(k)
   b=self.cache[k];m=min(n,len(b)-ofs);out.append(b[ofs:ofs+m]);self.pos+=m;n-=m
  return b''.join(out)
 def readinto(self,b):d=self.read(len(b));b[:len(d)]=d;return len(d)
r=RR();rows=[];center=(23.,-86.9);error=None
try:
 with h5py.File(r,'r') as h:
  lat=h['latitude'][:];lon=h['longitude'][:];west=((lon+180)%360)-180
  for k in range(5):
   ys=np.where(abs(lat-center[0])<=2.0)[0];xs=np.where(abs(west-center[1])<=2.0)[0]
   if not len(xs) or not len(ys):raise ValueError('no search grid')
   z=h['msl'][k,slice(ys.min(),ys.max()+1),slice(xs.min(),xs.max()+1)]
   # MSLP center constrained by continuity from initialized BEST at t=0.
   j,i=np.unravel_index(z.argmin(),z.shape);new=(float(lat[ys[j]]),float(west[xs[i]]))
   rows.append({'lead_h':k*6,'lat':new[0],'lon':new[1],'mslp_pa':float(z[j,i]),'search_center_prior':center})
   center=new
   print('POINT',rows[-1], 'bytes',r.n,flush=True)
except Exception as ex:error=repr(ex);print('ERROR',error,flush=True)
res={'url':URL,'seed_best_utc':'2024-10-09T00:00Z','seed_lat':23.,'seed_lon':-86.9,
 'rule':'within ±2 degree box of previous MSLP minimum, 6h steps; seeded by BEST at initialization only; exploratory, not vetted tracker',
 'points':rows,'error':error,'bytes':r.n,'requests':r.calls,'elapsed_s':round(time.monotonic()-r.t0,2),'full_file_bytes':SIZE}
with open('/content/aiwp_path_metrics.json','x') as f:json.dump(res,f,indent=2)
print('FINAL',json.dumps(res),flush=True)
