#!/usr/bin/env python3
"""M7 pilot: 2023-10 CHA; public GFS 100m vectors + SRTM DEM -> official ONNX.
No holdout observations opened. All outputs are compact station values on Colab.
"""
import csv, gzip, hashlib, io, json, math, os, time, traceback
from pathlib import Path
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import requests
import eccodes
import rasterio
from rasterio.io import MemoryFile
from rasterio.merge import merge
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from pyproj import Transformer
import onnxruntime as ort
from scipy.ndimage import zoom
ROOT=Path('/content/m7');ROOT.mkdir(exist_ok=True)
OUT=ROOT/'pilot';OUT.mkdir(exist_ok=True)
BASE='https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{day}/{hh}/atmos/gfs.t{hh}z.pgrb2.0p25.f{fhr:03d}'
HF='https://huggingface.co/linchensen/FuXi-CFD-model/resolve/98d2cb643ebddb752803919ad65eb2457314a2ae/fuxicfd-model/'
FILES=['model/fuxicfd_model.onnx','inference_example/normalization/scaler_input.npy','inference_example/normalization/scaler_output.npy','inference_example/data/inputs.npz']
WEIGHT_SHA='13daae67371d20a7ffb00db0a6c4679e580c28e77d2521eb7c2dcf9e80f20b3e'
SITE={'site':'CHA','lat':47.131761,'lon':7.054367}
FHRS=(6,12,24,48);PREV={6:5,12:11,24:23,48:45};FIELDS=(('UGRD','100 m above ground'),('VGRD','100 m above ground'))

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

def install_static():
 for rel in FILES:
  p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True)
  if not p.exists():
   with get(HF+rel+'?download=true',headers=None) as r, p.open('xb') as f:
    for chunk in r.iter_content(2**20):f.write(chunk)
  if rel.endswith('.onnx'):
   digest=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
   if digest!=WEIGHT_SHA:raise RuntimeError('wrong ONNX SHA '+digest)
 print('WEIGHT_SHA',WEIGHT_SHA,flush=True)

def dem():
 p=ROOT/'dem_CHA_v2.npy'
 if p.exists():return np.load(p)
 # SRTM 1 arcsecond tiles from USGS-derived public elevation-tiles-prod/skadi.
 # Domain: UTM zone 32N 301x301, 30 m pixels; station at centre.
 tr=Transformer.from_crs('EPSG:4326','EPSG:32632',always_xy=True)
 x,y=tr.transform(SITE['lon'],SITE['lat']);transform=from_origin(x-150.5*30,y+150.5*30,30,30)
 tiles=[]
 for lon in (6,7):
  name=f'N47E{lon:03d}.hgt.gz'
  raw=get('https://s3.amazonaws.com/elevation-tiles-prod/skadi/N47/'+name).content
  arr=np.frombuffer(gzip.decompress(raw),dtype='>i2')
  side=math.isqrt(arr.size)
  if side*side!=arr.size or side not in (1201,3601):raise ValueError('unexpected SRTM HGT tile size')
  tiles.append((arr.reshape(side,side).astype('float32'),from_origin(lon,48,1/(side-1),1/(side-1)),'EPSG:4326'))
 dst=np.full((301,301),np.nan,dtype='float32')
 for arr,src_transform,src_crs in tiles:
  part=np.full((301,301),np.nan,dtype='float32')
  reproject(arr,part,src_transform=src_transform,src_crs=src_crs,dst_transform=transform,dst_crs='EPSG:32632',src_nodata=-32768,dst_nodata=np.nan,resampling=Resampling.bilinear)
  good=np.isfinite(part);dst[good]=part[good]
 if not np.isfinite(dst).all():raise ValueError('DEM has gaps')
 np.save(p,dst)
 print('DEM_RANGE',float(dst.min()),float(dst.max()),'UTM32632',flush=True)
 return dst

def sample_field(message):
 gid=eccodes.codes_new_from_message(message)
 try:
  if (eccodes.codes_get(gid,'Ni'),eccodes.codes_get(gid,'Nj'))!=(1440,721):raise ValueError('GFS grid mismatch')
  grid=eccodes.codes_get_array(gid,'values').reshape(721,1440)
  tr=Transformer.from_crs('EPSG:32632','EPSG:4326',always_xy=True)
  cx,cy=Transformer.from_crs('EPSG:4326','EPSG:32632',always_xy=True).transform(SITE['lon'],SITE['lat'])
  xx=cx+np.linspace(-4000,4000,9); yy=cy+np.linspace(4000,-4000,9)
  lon,lat=tr.transform(*[a.ravel() for a in np.meshgrid(xx,yy)])
  iy=(90-np.asarray(lat))*4;ix=(np.asarray(lon)%360)*4
  i=iy.astype(int);j=ix.astype(int);a=iy-i;b=ix-j
  return ((1-a)*(1-b)*grid[i,j]+a*(1-b)*grid[i+1,j]+(1-a)*b*grid[i,j+1]+a*b*grid[i+1,j+1]).reshape(9,9).astype('float32')
 finally:eccodes.codes_release(gid)

def fetch_hour(init,fhr):
 url=BASE.format(day=init.strftime('%Y%m%d'),hh=init.strftime('%H'),fhr=fhr)
 idx=[line.split(':') for line in get(url+'.idx').text.splitlines()]
 found={(v[3],v[4]):n for n,v in enumerate(idx)}
 if not set(FIELDS)<=set(found):raise ValueError('100m fields missing '+str(set(FIELDS)-set(found)))
 out={}
 for field in FIELDS:
  n=found[field];lo=int(idx[n][1]);hi=int(idx[n+1][1])-1
  r=get(url,headers={'Range':f'bytes={lo}-{hi}'})
  if r.status_code!=206 or len(r.content)!=hi-lo+1:raise ValueError('bad GFS range')
  out[field[0]]=sample_field(r.content)
 return out

def run():
 start=time.monotonic();install_static();terrain=dem();roughness=np.full_like(terrain,.01)
 istats=np.load(ROOT/FILES[1],allow_pickle=True).item();ostats=np.load(ROOT/FILES[2],allow_pickle=True).item()
 sample=np.load(ROOT/FILES[3]);print('OFFICIAL_SAMPLE',[(k,sample[k].shape) for k in sample.files],flush=True)
 providers=['CUDAExecutionProvider','CPUExecutionProvider'];sess=ort.InferenceSession(str(ROOT/FILES[0]),providers=providers)
 if sess.get_providers()[0]!='CUDAExecutionProvider':raise RuntimeError('CUDA provider absent '+str(sess.get_providers()))
 print('CUDA_READY',sess.get_providers(),'SETUP_SEC',round(time.monotonic()-start,2),flush=True)
 static=np.stack([(terrain-istats['high_mean'][0])/istats['high_std'][0],(roughness-istats['high_mean'][1])/istats['high_std'][1]])
 static=zoom(static,(1,300/301,300/301),order=1).astype('float32')
 dates=[datetime(2023,10,1,tzinfo=timezone.utc)+timedelta(hours=6*n) for n in range(124)]
 expected=len(dates)*len(FHRS);done=set()
 checkpoint=OUT/'rows.jsonl'
 if checkpoint.exists():
  for line in checkpoint.read_text().splitlines():
   row=json.loads(line);done.add((row['init_utc'],row['fhr']))
 timings=[];request_seconds=0;failed=[]
 for seq,init in enumerate(dates,1):
  pending=[h for h in FHRS if (init.isoformat(),h) not in done]
  if not pending:continue
  t=time.monotonic()
  try:
   with ThreadPoolExecutor(max_workers=8) as pool:
    futures={pool.submit(fetch_hour,init,h):h for h in sorted(set(pending)|{PREV[h] for h in pending})}
    hours={futures[f]:f.result() for f in as_completed(futures)}
   request_seconds+=time.monotonic()-t
   for fhr in pending:
    mid=fhr-1/12;alpha=(mid-PREV[fhr])/(fhr-PREV[fhr]);a,b=hours[PREV[fhr]],hours[fhr]
    uv=np.stack([a[v]*(1-alpha)+b[v]*alpha for v in ('UGRD','VGRD')]);uv=(uv-istats['low_mean'][:,None,None])/istats['low_std'][:,None,None]
    uv=zoom(uv,(1,300/9,300/9),order=1).astype('float32')
    x=np.concatenate([uv,static])[None]
    t0=time.monotonic();pred=sess.run(None,{sess.get_inputs()[0].name:x})[0];elapsed=time.monotonic()-t0
    if pred.shape!=(1,27,4,300,300):raise ValueError('output shape '+str(pred.shape))
    u=pred[0,1,0,149,149]*ostats['std'][1,0]+ostats['mean'][1,0]
    v=pred[0,1,1,149,149]*ostats['std'][1,1]+ostats['mean'][1,1]
    row={'site':'CHA','init_utc':init.isoformat(),'fhr':fhr,'fx':float(math.hypot(u,v)),'u':float(u),'v':float(v),'infer_sec':elapsed}
    with checkpoint.open('a') as w:w.write(json.dumps(row)+'\n')
    timings.append(elapsed);done.add((init.isoformat(),fhr))
   if seq%8==0:print('PILOT_PROGRESS',seq,len(done),expected,'wall_sec',round(time.monotonic()-start,1),'mean_infer_sec',round(float(np.mean(timings)),3),flush=True)
  except Exception:
   failed.append({'init':init.isoformat(),'error':traceback.format_exc()});print('PILOT_ERROR',init,failed[-1]['error'][-900:],flush=True)
   # Fail fast: a missing GFS input must not silently shrink the pilot.
   raise
 if len(done)!=expected:raise RuntimeError(f'pilot incomplete {len(done)} != {expected}')
 summary={'site':'CHA','month':'2023-10','expected':expected,'completed':len(done),'failures':failed,'setup_and_total_wall_sec':time.monotonic()-start,'gfs_fetch_wall_sec':request_seconds,'inference_mean_sec':float(np.mean(timings)),'inference_median_sec':float(np.median(timings)),'inference_total_sec':float(np.sum(timings)),'sources':{'gfs':BASE,'srtm':'https://s3.amazonaws.com/elevation-tiles-prod/skadi/N47/','onnx_sha256':WEIGHT_SHA},'assumptions':['roughness constant 0.01 m (paper inflow z0), not observed ESA WorldCover map','9x9 coarse input points at 1km spacing, centred in UTM32N','301x301 DEM 30m UTM32N, official zoom to 300x300','output pixel (149,149), level 10 m from Supplementary Note 1.1']}
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2));(OUT/'pilot.done').write_text('success\n')
 print('PILOT_DONE',json.dumps(summary),flush=True)
if __name__=='__main__':
 try:run()
 except Exception:
  (OUT/'pilot.failed').write_text(traceback.format_exc());raise
