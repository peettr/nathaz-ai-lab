"""Run only on Colab: public NOAA HRRR f00 range fetch, hourly, immutable resume."""
import pathlib,datetime,urllib.request,io,concurrent.futures,time,traceback,json,argparse,os
import numpy as np
from eccodes import codes_new_from_message,codes_get_array,codes_get,codes_release
P=pathlib.Path('/content/l264a100/texas');OUT=P/'analysis';OUT.mkdir(exist_ok=True)
BASE='https://noaa-hrrr-bdp-pds.s3.amazonaws.com'
FIELDS={'u10':'UGRD:10 m above ground','v10':'VGRD:10 m above ground','t2m':'TMP:2 m above ground','mslp':'MSLMA:mean sea level'}
Y,X=0,810;H,W=440,408

def fetch(dt):
 key=dt.strftime('%Y%m%d%H');target=OUT/(key+'.npz')
 full=dt.day<=13
 names=['u10','v10','t2m','mslp'] if full else ['u10','v10']
 if target.exists():
  with np.load(target,allow_pickle=False) as z:
   if set(names).issubset(z.files) and all(z[k].shape==(H,W) and np.isfinite(z[k]).all() for k in names):return key,'cached',target.stat().st_size
  raise RuntimeError('Existing invalid file (do not overwrite): '+str(target))
 url=f"{BASE}/hrrr.{dt:%Y%m%d}/conus/hrrr.t{dt:%H}z.wrfsfcf00.grib2"
 for attempt in range(3):
  try:
   lines=urllib.request.urlopen(url+'.idx',timeout=60).read().decode().splitlines()
   parts=[x.split(':') for x in lines];vals={}
   for name in names:
    pat=FIELDS[name];matches=[i for i,row in enumerate(parts) if ':'.join(row[3:5])==pat]
    if len(matches)!=1:raise RuntimeError((key,pat,len(matches)))
    i=matches[0];start=int(parts[i][1]);end=int(parts[i+1][1])-1 if i+1<len(parts) else None
    if end is None:raise RuntimeError('no range end for '+pat)
    req=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}'})
    with urllib.request.urlopen(req,timeout=90) as resp:
     if resp.status!=206:raise RuntimeError(('status',resp.status,key,name))
     raw=resp.read()
    if len(raw)!=end-start+1:raise RuntimeError(('short read',key,name,len(raw)))
    g=codes_new_from_message(raw)
    if g is None:raise RuntimeError(('decode',key,name))
    ny,nx=int(codes_get(g,'Nj')),int(codes_get(g,'Ni'))
    if (ny,nx)!=(1059,1799):raise RuntimeError(('grid',key,name,ny,nx))
    a=np.asarray(codes_get_array(g,'values'),dtype=np.float32).reshape(ny,nx)[Y:Y+H,X:X+W].copy()
    codes_release(g)
    if not np.isfinite(a).all():raise RuntimeError(('nonfinite',key,name))
    vals[name]=a
   # Exclusive create avoids loss of prior completed output, zip with no large 工作站 file.
   with target.open('xb') as f:np.savez_compressed(f,**vals)
   return key,'new',target.stat().st_size
  except Exception:
   if attempt==2:raise
   time.sleep(2*(attempt+1))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--start',type=int,default=0);ap.add_argument('--count',type=int,default=1);ap.add_argument('--workers',type=int,default=8);a=ap.parse_args()
 base=datetime.datetime(2024,4,1);all_times=[base+datetime.timedelta(hours=i) for i in range(720)]
 ts=all_times[a.start:a.start+a.count]
 if len(ts)!=a.count:raise ValueError('outside April')
 start=time.monotonic();ok=0
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
  jobs={ex.submit(fetch,t):t for t in ts}
  for f in concurrent.futures.as_completed(jobs):
   try:
    key,state,nbytes=f.result();ok+=1
    with (P/'noaa_increment.jsonl').open('a') as o:o.write(json.dumps({'hour':key,'state':state,'bytes':nbytes})+'\n')
    if ok%12==0 or ok==len(ts):print('NOAA_PROGRESS',ok,'/',len(ts),'last',key,'seconds',round(time.monotonic()-start,1),flush=True)
   except BaseException as e:
    print('NOAA_FATAL',jobs[f],repr(e),flush=True);raise
 print('NOAA_COMPLETE',ok,'seconds',time.monotonic()-start,flush=True)
if __name__=='__main__':main()
