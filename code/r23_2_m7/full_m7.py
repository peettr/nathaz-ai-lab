#!/usr/bin/env python3
"""M7 full FX feature generation, exactly M5 paired keys, training+holdout.
Never reads observation values. Output JSONL checkpoint for scoring, no DEM/weights exported.
"""
import os,sys,csv,json,gzip,hashlib,math,time,traceback,tarfile
from pathlib import Path
from datetime import timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
import numpy as np,pandas as pd,requests,eccodes,rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject,Resampling
from pyproj import Transformer
from scipy.ndimage import zoom
import onnxruntime as ort
ROOT=Path('/content/m7');OUT=ROOT/'full';OUT.mkdir(exist_ok=True)
BASE='https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{day}/{hh}/atmos/gfs.t{hh}z.pgrb2.0p25.f{fhr:03d}'
PREV={6:5,12:11,24:23,48:45};FIELDS=(('UGRD','100 m above ground'),('VGRD','100 m above ground'))
SITES=json.loads((ROOT/'stations.json').read_text());assert len(SITES)==12
SITE_BY={s['site']:s for s in SITES}
STAGE=ROOT/'score_stage_archive.tgz'

def get(url,headers=None):
 for k in range(4):
  try:
   r=requests.get(url,headers=headers,timeout=(15,60))
   if r.status_code in (200,206):return r
   if r.status_code not in (429,500,502,503,504):r.raise_for_status()
  except Exception:
   if k==3:raise
  time.sleep(k+1)
 raise RuntimeError(url)

def prepare_keys():
 # Only exact frozen M5 pairs are used; no change to sample population.
 with tarfile.open(STAGE) as t:
  for name in ('train_pairs.parquet','test_pairs.parquet'):
   with t.extractfile(name) as f:pass
  train=pd.read_parquet(t.extractfile('train_pairs.parquet'))
  test=pd.read_parquet(t.extractfile('test_pairs.parquet'))
 a=pd.concat([train[['site','init_utc','fhr']],test[['site','init_utc','fhr']]],ignore_index=True)
 a['init_utc']=pd.to_datetime(a.init_utc,utc=True)
 if a.duplicated(['site','init_utc','fhr']).any():raise ValueError('duplicate frozen M5 keys')
 if set(a.site)!=set(SITE_BY) or set(a.fhr)!={6,12,24,48}:raise ValueError('roster/lead mismatch')
 print('KEYS',len(train),len(test),len(a),'INITS',a.init_utc.nunique(),flush=True)
 return {(r.site,r.init_utc.to_pydatetime().isoformat(),int(r.fhr)) for r in a.itertuples(index=False)}

def sample_grid(grid,site):
 tr=Transformer.from_crs('EPSG:4326',f'EPSG:{32600+int((site["lon"]+180)//6)+1}',always_xy=True)
 back=Transformer.from_crs(tr.target_crs,'EPSG:4326',always_xy=True)
 cx,cy=tr.transform(site['lon'],site['lat']); xx=cx+np.linspace(-4000,4000,9);yy=cy+np.linspace(4000,-4000,9)
 x,y=np.meshgrid(xx,yy);lon,lat=back.transform(x.ravel(),y.ravel())
 yi=(90-np.asarray(lat))*4;xi=(np.asarray(lon)%360)*4;i=yi.astype(int);j=xi.astype(int);a=yi-i;b=xi-j
 return ((1-a)*(1-b)*grid[i,j]+a*(1-b)*grid[i+1,j]+(1-a)*b*grid[i,j+1]+a*b*grid[i+1,j+1]).reshape(9,9).astype('float32')

def fetch_field(init,fhr):
 url=BASE.format(day=init.strftime('%Y%m%d'),hh=init.strftime('%H'),fhr=fhr)
 idx=[x.split(':') for x in get(url+'.idx').text.splitlines()]; found={(v[3],v[4]):n for n,v in enumerate(idx)}
 if not set(FIELDS)<=set(found):raise ValueError('missing 100m fields '+str(set(FIELDS)-set(found)))
 out={}
 for v,lev in FIELDS:
  n=found[v,lev];lo=int(idx[n][1]);hi=int(idx[n+1][1])-1
  r=get(url,headers={'Range':f'bytes={lo}-{hi}'})
  if r.status_code!=206 or len(r.content)!=hi-lo+1:raise ValueError('bad Range')
  g=eccodes.codes_new_from_message(r.content)
  try:
   if (eccodes.codes_get(g,'Ni'),eccodes.codes_get(g,'Nj'))!=(1440,721):raise ValueError('grid mismatch')
   out[v]=eccodes.codes_get_array(g,'values').reshape(721,1440)
  finally:eccodes.codes_release(g)
 return out

TILE_CACHE={}
def tile(lat,lon):
 ident=(lat,lon)
 if ident not in TILE_CACHE:
  ns=f'N{lat:02d}' if lat>=0 else f'S{-lat:02d}'; ew=f'E{lon:03d}' if lon>=0 else f'W{-lon:03d}'
  raw=get(f'https://s3.amazonaws.com/elevation-tiles-prod/skadi/{ns}/{ns}{ew}.hgt.gz').content
  arr=np.frombuffer(gzip.decompress(raw),'>i2');side=math.isqrt(arr.size)
  if side not in (1201,3601) or side**2!=arr.size:raise ValueError('SRTM shape')
  TILE_CACHE[ident]=(arr.reshape(side,side).astype('float32'),from_origin(lon,lat+1,1/(side-1),1/(side-1)))
 return TILE_CACHE[ident]

def dem(site):
 p=ROOT/f'dem_{site["site"]}_v2.npy'
 if p.exists():return np.load(p)
 epsg=f'EPSG:{32600+int((site["lon"]+180)//6)+1}'
 fw=Transformer.from_crs('EPSG:4326',epsg,always_xy=True);back=Transformer.from_crs(epsg,'EPSG:4326',always_xy=True)
 cx,cy=fw.transform(site['lon'],site['lat']);transform=from_origin(cx-150.5*30,cy+150.5*30,30,30)
 corners=[back.transform(cx+dx,cy+dy) for dx in (-4550,4550) for dy in (-4550,4550)]
 lons=range(math.floor(min(x for x,y in corners)),math.floor(max(x for x,y in corners))+1)
 lats=range(math.floor(min(y for x,y in corners)),math.floor(max(y for x,y in corners))+1)
 dest=np.full((301,301),np.nan,dtype='float32')
 for la in lats:
  for lo in lons:
   src,tf=tile(la,lo);part=np.full_like(dest,np.nan)
   reproject(src,part,src_transform=tf,src_crs='EPSG:4326',dst_transform=transform,dst_crs=epsg,src_nodata=-32768,dst_nodata=np.nan,resampling=Resampling.bilinear)
   valid=np.isfinite(part);dest[valid]=part[valid]
 if not np.isfinite(dest).all():raise ValueError('DEM missing '+site['site'])
 if not 0<dest.min()<dest.max()<5000:raise ValueError('DEM implausible '+site['site']+str((dest.min(),dest.max())))
 np.save(p,dest);print('DEM',site['site'],float(dest.min()),float(dest.max()),float(dest[150,150]),flush=True)
 return dest

def run():
 started=time.monotonic();keys=prepare_keys();checkpoint=OUT/'fx_rows.jsonl'
 prior={}
 if checkpoint.exists():
  for line in checkpoint.read_text().splitlines():
   row=json.loads(line);k=(row['site'],row['init_utc'],row['fhr'])
   if k in prior:raise ValueError('duplicate checkpoint key')
   prior[k]=row
 if not set(prior)<=keys:raise ValueError('checkpoint keys outside frozen cohort')
 in_stats=np.load(ROOT/'inference_example/normalization/scaler_input.npy',allow_pickle=True).item()
 out_stats=np.load(ROOT/'inference_example/normalization/scaler_output.npy',allow_pickle=True).item()
 model=ROOT/'model/fuxicfd_model.onnx'
 with model.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
 if digest!='13daae67371d20a7ffb00db0a6c4679e580c28e77d2521eb7c2dcf9e80f20b3e':raise ValueError('ONNX hash')
 sess=ort.InferenceSession(str(model),providers=['CUDAExecutionProvider','CPUExecutionProvider'])
 if sess.get_providers()[0]!='CUDAExecutionProvider':raise ValueError('CUDA unavailable')
 static={}
 for site in SITES:
  d=dem(site);r=np.full_like(d,.01)
  s=np.stack([(d-in_stats['high_mean'][0])/in_stats['high_std'][0],(r-in_stats['high_mean'][1])/in_stats['high_std'][1]])
  static[site['site']]=zoom(s,(1,300/301,300/301),order=1).astype('float32')
 print('STATIC_READY',len(static),'seconds',round(time.monotonic()-started,2),flush=True)
 init_map={}
 for site,init,fhr in keys-prior.keys():init_map.setdefault(init,{}).setdefault(fhr,[]).append(site)
 total=len(keys);done=len(prior);errors=[];times=[]
 for seq,init_s in enumerate(sorted(init_map),1):
  init=pd.Timestamp(init_s).to_pydatetime();needed=init_map[init_s]
  t=time.monotonic()
  try:
   with ThreadPoolExecutor(max_workers=8) as pool:
    fs={pool.submit(fetch_field,init,h):h for h in sorted(set(needed)|{PREV[h] for h in needed})}
    grids={fs[f]:f.result() for f in as_completed(fs)}
   for fhr,sites in sorted(needed.items()):
    alpha=(fhr-1/12-PREV[fhr])/(fhr-PREV[fhr])
    for site in sorted(sites):
     A=grids[PREV[fhr]];B=grids[fhr]
     uv=np.stack([(sample_grid(A[v],SITE_BY[site])*(1-alpha)+sample_grid(B[v],SITE_BY[site])*alpha) for v in ('UGRD','VGRD')])
     uv=(uv-in_stats['low_mean'][:,None,None])/in_stats['low_std'][:,None,None]
     uv=zoom(uv,(1,300/9,300/9),order=1).astype('float32')
     x=np.concatenate([uv,static[site]])[None]
     t0=time.monotonic();pred=sess.run(None,{sess.get_inputs()[0].name:x})[0];elapsed=time.monotonic()-t0
     if pred.shape!=(1,27,4,300,300):raise ValueError('output shape')
     u=pred[0,1,0,149,149]*out_stats['std'][1,0]+out_stats['mean'][1,0]
     v=pred[0,1,1,149,149]*out_stats['std'][1,1]+out_stats['mean'][1,1]
     row={'site':site,'init_utc':init_s,'fhr':fhr,'fx':float(math.hypot(u,v)),'u':float(u),'v':float(v),'infer_sec':elapsed}
     with checkpoint.open('a') as w:w.write(json.dumps(row)+'\n')
     done+=1;times.append(elapsed)
   if seq%12==0:print('FULL_PROGRESS',seq,len(init_map),done,total,'last_init_sec',round(time.monotonic()-t,1),'elapsed_sec',round(time.monotonic()-started,1),flush=True)
  except Exception:
   errors.append({'init':init_s,'error':traceback.format_exc()});print('FULL_ERROR',init_s,errors[-1]['error'][-1000:],flush=True)
   raise
 if done!=total:raise ValueError('incomplete '+str((done,total)))
 summary={'expected':total,'complete':done,'initializations':len(init_map),'new_inference_count':len(times),'mean_inference_sec':float(np.mean(times)),'wall_sec':time.monotonic()-started,'errors':errors}
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2));(OUT/'full.done').write_text('success\n')
 print('FULL_DONE',json.dumps(summary),flush=True)
if __name__=='__main__':
 try:run()
 except Exception:
  (OUT/'full.failed').write_text(traceback.format_exc());raise
