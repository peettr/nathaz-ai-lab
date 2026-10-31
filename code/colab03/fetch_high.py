"""VM-only bounded HRRR pressure-level analysis via NOAA public .idx ranges."""
import concurrent.futures,datetime,io,json,pathlib,time,urllib.request
import numpy as np
from eccodes import codes_new_from_message,codes_get_array,codes_get,codes_release
P=pathlib.Path('/content/l264a100/texas');D=P/'analysis_high';D.mkdir(exist_ok=True)
BASE='https://noaa-hrrr-bdp-pds.s3.amazonaws.com';LEVELS=(300,500,700,850,925)
def one(i):
 dt=datetime.datetime(2024,4,1)+datetime.timedelta(hours=i);key=dt.strftime('%Y%m%d%H');dest=D/(key+'.npz')
 if dest.exists():
  with np.load(dest,allow_pickle=False) as z:assert z['air'].shape==(10,440,408)
  return key,'cached'
 u=f'{BASE}/hrrr.{dt:%Y%m%d}/conus/hrrr.t{dt:%H}z.wrfprsf00.grib2';lines=urllib.request.urlopen(u+'.idx',timeout=45).read().decode().splitlines();parts=[s.split(':') for s in lines]
 vals=[]
 for var in ('HGT','TMP'):
  for level in LEVELS:
   match=[j for j,row in enumerate(parts) if ':'.join(row[3:5])==f'{var}:{level} mb' and 'anl' in row]
   if len(match)!=1:raise RuntimeError((key,var,level,match))
   j=match[0];start=int(parts[j][1]);end=int(parts[j+1][1])-1
   req=urllib.request.Request(u,headers={'Range':f'bytes={start}-{end}'})
   with urllib.request.urlopen(req,timeout=60) as resp:
    if resp.status!=206:raise RuntimeError((key,resp.status))
    raw=resp.read()
   msg=codes_new_from_message(raw);ny,nx=int(codes_get(msg,'Nj')),int(codes_get(msg,'Ni'))
   if (ny,nx)!=(1059,1799):raise RuntimeError((ny,nx))
   field=np.asarray(codes_get_array(msg,'values'),dtype=np.float32).reshape(ny,nx)[:440,810:1218].copy();codes_release(msg)
   vals.append(field)
 arr=np.stack(vals);assert np.isfinite(arr).all()
 with dest.open('xb') as f:np.savez_compressed(f,air=arr)
 return key,'new'
def main():
 # 00Z 01-10, 72 lead hours => through Apr 13 00Z.
 hours=range(0,289);t=time.monotonic()
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
  fs={ex.submit(one,i):i for i in hours}
  for n,f in enumerate(concurrent.futures.as_completed(fs),1):
   try:key,state=f.result()
   except Exception as e:print('HIGH_FATAL',fs[f],repr(e),flush=True);raise
   if n%12==0 or n==len(fs):print('HIGH_PROGRESS',n,'/',len(fs),key,state,'seconds',round(time.monotonic()-t),flush=True)
 (P/'high_fetch.done').write_text('289 hours\n')
if __name__=='__main__':main()
