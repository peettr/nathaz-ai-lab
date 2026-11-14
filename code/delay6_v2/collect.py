#!/usr/bin/env python3
"""Delay-6 GFS feature extraction; never uses observed wind for feature generation."""
import csv, io, json, math, os, tarfile, time, traceback
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np, pandas as pd, requests, eccodes
from pyproj import Transformer
R=Path('/content/delay6'); O=R/'gfs';O.mkdir(parents=True,exist_ok=True)
BASE='https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{day}/{hh}/atmos/gfs.t{hh}z.pgrb2.0p25.f{fhr:03d}'
LEVELS=(1000,975,950,925,900,850,800,750,700,650,600,550,500)
FHRS=(6,12,24,48); TARGET={6:12,12:18,24:30,48:54};PREV={12:11,18:17,30:29,54:51}
FIELDS=[('UGRD','10 m above ground'),('VGRD','10 m above ground'),('HGT','surface'),('UGRD','100 m above ground'),('VGRD','100 m above ground')]+[(v,f'{p} mb') for p in LEVELS for v in ('UGRD','VGRD','HGT')]
SITES=json.loads((R/'stations.json').read_text());assert len(SITES)==12

def get(url,headers=None):
 for attempt in range(4):
  try:
   r=requests.get(url,headers=headers,timeout=(15,65))
   if r.status_code in (200,206):return r
   if r.status_code not in (429,500,502,503,504):r.raise_for_status()
  except Exception:
   if attempt==3:raise
  time.sleep(attempt+1)
 raise RuntimeError(url)

def keys():
 with tarfile.open(R/'score_stage_archive.tgz') as t:
  tr=pd.read_parquet(t.extractfile('train_pairs.parquet'))
  te=pd.read_parquet(t.extractfile('test_pairs.parquet'))
 for d in (tr,te):
  d['init_utc']=pd.to_datetime(d.init_utc,utc=True);d['valid_end_utc']=pd.to_datetime(d.valid_end_utc,utc=True)
  assert (d.valid_end_utc==d.init_utc+pd.to_timedelta(d.fhr,unit='h')).all()
  assert not d.duplicated(['site','init_utc','fhr']).any()
  d['issue_utc']=d.init_utc+pd.Timedelta(hours=4)
  d['init_new']=d.init_utc-pd.Timedelta(hours=6)
  assert (d.init_new+pd.Timedelta(hours=6)<=d.issue_utc).all()
  assert (d.valid_end_utc==d.init_new+pd.to_timedelta(d.fhr+6,unit='h')).all()
 tr=tr[(tr.valid_end_utc<pd.Timestamp('2024-01-01',tz='UTC'))&(tr.issue_utc<pd.Timestamp('2023-12-31 18:00',tz='UTC'))]
 te=te[te.issue_utc>=pd.Timestamp('2024-01-01',tz='UTC')]
 assert len(tr)==17604 and len(te)==17252,(len(tr),len(te))
 allrows=pd.concat([tr,te],ignore_index=True)[['site','init_utc','init_new','valid_end_utc','issue_utc','fhr']]
 assert not allrows.duplicated(['site','init_utc','fhr']).any()
 return allrows

def sample(grid,lat,lon):
 y=(90-np.asarray(lat))*4;x=(np.asarray(lon)%360)*4;i=y.astype(int);j=x.astype(int);a=y-i;b=x-j
 return ((1-a)*(1-b)*grid[i,j]+a*(1-b)*grid[i+1,j]+(1-a)*b*grid[i,j+1]+a*b*grid[i+1,j+1]).astype('float32')

COORD=[]
for s in SITES:
 tr=Transformer.from_crs('EPSG:4326',f'EPSG:{32600+int((s["lon"]+180)//6)+1}',always_xy=True)
 back=Transformer.from_crs(tr.target_crs,'EPSG:4326',always_xy=True)
 cx,cy=tr.transform(s['lon'],s['lat']);xx=cx+np.linspace(-4000,4000,9);yy=cy+np.linspace(4000,-4000,9)
 lo,la=back.transform(*[x.ravel() for x in np.meshgrid(xx,yy)])
 COORD.append((np.r_[s['lat'],la],np.r_[s['lon'],lo]))
LATS=np.concatenate([x[0] for x in COORD]);LONS=np.concatenate([x[1] for x in COORD]);NS=len(SITES)

def hour(init,fhr):
 url=BASE.format(day=init.strftime('%Y%m%d'),hh=init.strftime('%H'),fhr=fhr)
 idx=[v.split(':') for v in get(url+'.idx').text.splitlines()];found={(v[3],v[4]):i for i,v in enumerate(idx)}
 if not set(FIELDS)<=set(found):raise ValueError('missing fields '+str(set(FIELDS)-set(found)))
 def one(field):
  n=found[field];lo=int(idx[n][1]);hi=int(idx[n+1][1])-1
  r=get(url,{'Range':f'bytes={lo}-{hi}'})
  if r.status_code!=206 or len(r.content)!=hi-lo+1:raise ValueError('range mismatch '+str(field))
  gid=eccodes.codes_new_from_message(r.content)
  try:
   if (eccodes.codes_get(gid,'Ni'),eccodes.codes_get(gid,'Nj'))!=(1440,721) or eccodes.codes_get(gid,'latitudeOfFirstGridPointInDegrees')!=90:raise ValueError('GFS grid mismatch')
   return field,sample(eccodes.codes_get_array(gid,'values').reshape(721,1440),LATS,LONS)
  finally:eccodes.codes_release(gid)
 with ThreadPoolExecutor(max_workers=12) as pool:return dict(pool.map(one,FIELDS))

def derive(data,siteidx):
 i=siteidx*82;s=SITES[siteidx]; zsurf=float(data['HGT','surface'][i]);zs=s['z_site_asl']
 u=float(data['UGRD','10 m above ground'][i]);v=float(data['VGRD','10 m above ground'][i]);raw=math.hypot(u,v)
 layers=[]
 for p in LEVELS:
  h=float(data['HGT',f'{p} mb'][i]);a=float(data['UGRD',f'{p} mb'][i]);b=float(data['VGRD',f'{p} mb'][i])
  if np.isfinite(h) and np.isfinite(a) and np.isfinite(b) and h>=zsurf:layers.append((h,a,b))
 layers.sort()
 if zs<=zsurf:eu,ev=u,v
 elif not layers:raise ValueError('no above-ground pressure layer '+s['site'])
 else:
  anchors=[(zsurf+10,u,v)]+[x for x in layers if x[0]>zsurf+10]
  if zs<=anchors[0][0]:eu,ev=anchors[0][1:]
  elif zs>=anchors[-1][0]:raise ValueError('station above 500hPa')
  else:
   j=next(j for j in range(1,len(anchors)) if anchors[j][0]>=zs);low,high=anchors[j-1:j+1];a=(zs-low[0])/(high[0]-low[0]);eu=low[1]*(1-a)+high[1]*a;ev=low[2]*(1-a)+high[2]*a
 return raw,math.hypot(eu,ev),zsurf,zs-zsurf

def run():
 a=keys();by={}
 for row in a.itertuples(index=False):by.setdefault(row.init_new,{}).setdefault(int(row.fhr),set()).add(row.site)
 dates=sorted(by);limit=int(os.environ.get('DELAY6_LIMIT','0'));dates=dates[:limit] if limit else dates
 start=time.monotonic()
 for n,stamp in enumerate(dates,1):
  init=stamp.to_pydatetime();target=O/f'{init:%Y%m%d%H}.npz'
  if target.exists():continue
  t=time.monotonic();needed=by[stamp];hrs=sorted({h for f in needed for h in (PREV[TARGET[f]],TARGET[f])})
  with ThreadPoolExecutor(max_workers=6) as pool:
   fs={pool.submit(hour,init,h):h for h in hrs};data={fs[f]:f.result() for f in as_completed(fs)}
  rows=[];uv=[]
  for fhr,sites in sorted(needed.items()):
   new=TARGET[fhr];alpha=(new-1/12-PREV[new])/(new-PREV[new]);d0=data[PREV[new]];d1=data[new]
   interp={field:d0[field]*(1-alpha)+d1[field]*alpha for field in FIELDS}
   for site in sorted(sites):
    j=next(j for j,s in enumerate(SITES) if s['site']==site)
    raw,v1,zsurf,dz=derive(interp,j)
    coarse=np.stack([interp[v,'100 m above ground'][j*82+1:(j+1)*82].reshape(9,9) for v in ('UGRD','VGRD')])
    assert np.isfinite(coarse).all() and np.isfinite([raw,v1,dz]).all()
    rows.append((site,init.isoformat(),fhr,new,raw,v1,zsurf,dz));uv.append(coarse)
  tmp=target.with_suffix('.partial')
  with tmp.open('wb') as f:np.savez_compressed(f,rows=np.array(rows,dtype=object),uv=np.array(uv,dtype='float32'))
  tmp.rename(target)
  with (R/'collect_progress.jsonl').open('a') as f:f.write(json.dumps({'init_new':init.isoformat(),'count':len(rows),'seconds':time.monotonic()-t,'seq':n})+'\n')
  if n%5==0:print('COLLECT',n,len(dates),'rows',len(rows),'wall',round(time.monotonic()-start,1),flush=True)
 print('COLLECT_DONE',len(dates),sum(len(np.load(p,allow_pickle=True)['rows']) for p in O.glob('*.npz')),flush=True)
if __name__=='__main__':
 try:run()
 except Exception:
  (R/'collect.failed').write_text(traceback.format_exc());raise
