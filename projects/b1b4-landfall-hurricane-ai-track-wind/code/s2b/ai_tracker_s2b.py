#!/usr/bin/env python3
"""Single-cycle preregistered 850 hPa circulation tracker; bounded S3 Range reads."""
import csv,io,json,math,sys,time,collections
from pathlib import Path
from datetime import datetime,timedelta
import requests,h5py,numpy as np
from scipy.ndimage import uniform_filter,uniform_filter1d
HERE=Path(__file__).resolve().parent
BLOCK=262144
class Range(io.RawIOBase):
 def __init__(self,url,size):
  self.url=url;self.size=size;self.pos=0;self.bytes=0;self.calls=0;self.cache=collections.OrderedDict();self.start=time.monotonic();self.session=requests.Session()
 def readable(self):return True
 def seekable(self):return True
 def tell(self):return self.pos
 def seek(self,o,w=0):self.pos=o if w==0 else self.pos+o if w==1 else self.size+o;return self.pos
 def readinto(self,b):
  x=self.read(len(b));b[:len(x)]=x;return len(x)
 def read(self,n=-1):
  if n<0:n=self.size-self.pos
  chunks=[]
  while n>0 and self.pos<self.size:
   k=self.pos//BLOCK;off=self.pos%BLOCK
   if k not in self.cache:
    if self.bytes>=1_300_000_000 or self.calls>=6000 or time.monotonic()-self.start>900:raise RuntimeError('range budget reached')
    a=k*BLOCK;r=self.session.get(self.url,headers={'Range':f'bytes={a}-{min(a+BLOCK-1,self.size-1)}'},timeout=45)
    if r.status_code!=206:raise RuntimeError(f'HTTP Range {r.status_code}')
    self.cache[k]=r.content;self.calls+=1;self.bytes+=len(r.content)
    if len(self.cache)>256:self.cache.popitem(last=False)
   else:self.cache.move_to_end(k)
   data=self.cache[k];m=min(n,len(data)-off);chunks.append(data[off:off+m]);self.pos+=m;n-=m
  return b''.join(chunks)

def track(event,lead,model):
 events={r['name']:r for r in csv.DictReader((HERE.parent.parent/'events_verified.csv').open())};ev=events[event]
 land=datetime.fromisoformat(ev['landfall_utc']); t=land-timedelta(hours=lead);cycle=t.replace(hour=12 if t.hour>=12 else 0,minute=0,second=0,microsecond=0)
 sid=ev['atcf_id'].lower()
 sys.path.insert(0,str(HERE.parent));import chain_b_s2a as chain_b
 a,url_a=chain_b.load_a(sid);initial,err=chain_b.get_initial(a,cycle)
 if err:raise ValueError(err)
 prefix={'PANG':'PANG_v100_GFS','FOUR':'FOUR_v200_GFS','GRAP':'GRAP_v100_GFS'}[model]
 key=f'{prefix}/{cycle.year}/{cycle:%m%d}/{prefix}_{cycle:%Y%m%d%H}_f000_f240_06.nc';url='https://noaa-oar-mlwp-data.s3.amazonaws.com/'+key
 resp=requests.head(url,timeout=30);resp.raise_for_status();size=int(resp.headers['Content-Length']);reader=Range(url,size)
 center=(initial['seed_lat'],initial['seed_lon']);rows=[];failure=None
 with h5py.File(reader,'r') as h:
  lat=np.array(h['latitude'][:]);lon=np.array(h['longitude'][:]);lon=((lon+180)%360)-180;lev=np.array(h['level'][:]);zi=int(np.argmin(abs(lev-850)))
  if abs(lev[zi]-850)>1:raise ValueError(f'850 hPa unavailable: {lev}')
  u=h['u'];v=h['v'];msl=h['msl']
  for step in range(min(len(h['time']),math.ceil((land+timedelta(hours=12)-cycle).total_seconds()/21600)+1)):
   tt=cycle+timedelta(hours=6*step)
   # Deliberately full 350-km neighborhood plus 200-km circulation footprint.
   yids=np.where(abs(lat-center[0])<6)[0];xids=np.where(abs(lon-center[1])<7)[0]
   if not len(xids) or not len(yids):failure=f'out of grid at {step}';break
   ys=slice(yids.min(),yids.max()+1);xs=slice(xids.min(),xids.max()+1)
   ulat=lat[ys];ulon=lon[xs];du=np.array(u[step,zi,ys,xs]);dv=np.array(v[step,zi,ys,xs])
   dy=float(lat[1]-lat[0])*111200;dx=np.cos(np.deg2rad(center[0]))*float(lon[1]-lon[0])*111200
   vort=np.gradient(dv,dx,axis=1)-np.gradient(du,dy,axis=0)
   # Frozen 5x5 smoothing and 200 km disk-mean vorticity. A disk of variable grid radius per latitude.
   vs=uniform_filter(vort,size=5,mode='nearest')
   rad_y=int(200000/abs(dy));rad_x=int(200000/abs(dx)); yy,xx=np.mgrid[-rad_y:rad_y+1,-rad_x:rad_x+1]
   kernel=((xx*dx)**2+(yy*dy)**2<=200000**2).astype(float);kernel/=kernel.sum()
   from scipy.signal import fftconvolve
   mean=fftconvolve(vs,kernel,mode='same')
   YY,XX=np.meshgrid(ulat,ulon,indexing='ij')
   dist=np.sqrt(((YY-center[0])*111.2)**2+((XX-center[1])*111.2*np.cos(np.deg2rad(center[0])))**2)
   score=np.where(dist<=350,mean,-np.inf)
   candidates=np.argsort(score.ravel())[::-1]
   selected=None
   for flat in candidates[:300]:
    j,i=np.unravel_index(flat,score.shape)
    if not np.isfinite(score[j,i]) or score[j,i]<=0:break
    yy=(YY-YY[j,i])*111.2;xx=(XX-XX[j,i])*111.2*np.cos(np.deg2rad(YY[j,i]));rr=np.hypot(xx,yy)
    ring=(rr>=100)&(rr<=400)&(rr>0)
    tangent=np.mean((-du*yy+dv*xx)[ring]/rr[ring]) if np.any(ring) else -1
    if tangent>0:selected=(j,i,float(tangent));break
   if selected is None:failure=f'no cyclonic circulation at {step}';break
   j,i,tangent=selected; new=(float(ulat[j]),float(ulon[i]));mslp=float(msl[step,ys,xs][j,i])
   rows.append(dict(event=event,model=model,nominal_lead_h=lead,init_utc=cycle.isoformat(),valid_utc=tt.isoformat(),lat=new[0],lon=new[1],vorticity_200km=float(score[j,i]),tangential_ms=tangent,mslp_pa=mslp))
   center=new
   print('STEP',step,tt.isoformat(),new,'bytes',reader.bytes,flush=True)
   (HERE/f'checkpoint_{event.lower()}_{model.lower()}_{lead}.json').write_text(json.dumps({'points':rows,'bytes':reader.bytes,'calls':reader.calls,'elapsed_s':time.monotonic()-reader.start,'failure':failure},indent=2))
 record=dict(event=event,model=model,lead=lead,init_utc=cycle.isoformat(),url=url,bytes=reader.bytes,calls=reader.calls,elapsed_s=time.monotonic()-reader.start,points=rows,failure=failure)
 path=HERE/f'track_{event.lower()}_{model.lower()}_{lead}.json';path.write_text(json.dumps(record,indent=2))
 print('COMPLETE',path,reader.bytes,failure,flush=True)
if __name__=='__main__':track(sys.argv[1],int(sys.argv[2]),sys.argv[3])
