#!/usr/bin/env python3
"""Frozen B2 v2 paired CLIMADA H08 catalogue sweep; outputs per-batch NPZ.
Run on owned Colab CPU; source arrays remain remote, small output is downloaded.
"""
import argparse, csv, io, math, pathlib, time, zipfile
import numpy as np, xarray as xr
from climada.hazard.trop_cyclone.trop_cyclone_windfields import tctrack_to_si, _compute_windfields, MODEL_VANG
ROOT=pathlib.Path('/content/b2'); SITES=np.array([(float(x['lat']),float(x['lon'])) for x in csv.DictReader(open('/content/b2/sites.csv'))]);
R=6371.0

def dist(lat,lon):
 a=np.radians(np.asarray(lat)[...,None]-SITES[:,0]); b=np.radians(np.asarray(lon)[...,None]-SITES[:,1]);
 q=np.sin(a/2)**2+np.cos(np.radians(np.asarray(lat)[...,None]))*np.cos(np.radians(SITES[:,0]))*np.sin(b/2)**2
 return 2*R*np.arcsin(np.sqrt(np.maximum(0,q)))

def near(lat,lon):
 # Endpoint buffer exceeds half the inter-node displacement, so no crossed
 # 500-km segment is discarded even with a 6-h-long RAFT time step.
 endpoints=dist(lat,lon); spacing=2*R*np.arcsin(np.sqrt(np.maximum(0,np.sin(np.radians(np.diff(lat))/2)**2+np.cos(np.radians(lat[:-1]))*np.cos(np.radians(lat[1:]))*np.sin(np.radians(np.diff(lon))/2)**2)))
 pad=max(spacing,default=0)/2
 return bool(np.min(endpoints)<=500+pad)

def make_track(lat,lon,pc,rmw,vmax,step_hours,source):
 n=len(lat); nt=(n-1)*int(step_hours*4)+1
 old=np.arange(n)*step_hours*4; grid=np.arange(nt)
 def inter(a):return np.interp(grid,old,a)
 la=inter(lat);lo=inter(np.unwrap(np.radians(lon)))*180/np.pi;pr=inter(pc);ra=inter(rmw)
 vmax=inter(vmax);tm=np.datetime64('2000-01-01T00:00')+grid.astype('timedelta64[m]')*15
 ds=xr.Dataset(data_vars={'lat':('time',la),'lon':('time',lo),'central_pressure':('time',pr),'radius_max_wind':('time',ra),
   'max_sustained_wind':('time',vmax),'environmental_pressure':('time',np.full(nt,1010.0)),
   'time_step':('time',np.full(nt,0.25))},coords={'time':tm},
   attrs={'max_sustained_wind_unit':'knots' if source=='raft' else 'm/s','central_pressure_unit':'mbar'})
 return ds

def predict(ds):
 out=[]
 for env in (1010.,1005.,1015.):
  ds['environmental_pressure'].values[:]=env
  si=tctrack_to_si(ds)
  vectors,ix=_compute_windfields(si,SITES,MODEL_VANG['H08'],max_dist_eye_km=300)
  peak=np.zeros(19,dtype='float32');ratio=np.full(19,np.nan,dtype='float32')
  if len(ix):
   sp=np.linalg.norm(vectors,axis=2)
   for j,k in enumerate(ix):
    t=int(np.argmax(sp[:,j]));peak[k]=sp[t,j]*1.07
    rad=float(ds['radius_max_wind'].values[t]);ratio[k]=float(dist(float(ds['lat'].values[t]),float(ds['lon'].values[t]))[k]*1000/(rad*1852)) if rad>0 else np.nan
  out.append((peak,ratio))
 return out

def raft():
 d=xr.open_dataset(ROOT/'RAFT.NA.v20231016.nc');fields={v:d[v].values for v in ('lat','lon','vmax','mslp','rmax','storm_ID')}
 for i in range(40000):
  valid=(np.isfinite(fields['lat'][i])&np.isfinite(fields['lon'][i])&np.isfinite(fields['mslp'][i])&(fields['mslp'][i]>0)&(fields['rmax'][i]>0)&(fields['vmax'][i]>0))
  idx=np.where(valid)[0]
  if len(idx)<2:yield i,None;continue
  # Do not bridge interior missing nodes.
  if np.any(np.diff(idx)!=1):yield i,None;continue
  lat=fields['lat'][i,idx].astype(float);lon=fields['lon'][i,idx].astype(float)
  if not near(lat,lon):yield i,None;continue
  yield i,(lat,lon,fields['mslp'][i,idx].astype(float),fields['rmax'][i,idx].astype(float),fields['vmax'][i,idx].astype(float),6)

def storm():
 with zipfile.ZipFile(ROOT/'STORMV4.zip') as z:
  names=sorted((x for x in z.namelist() if '_NA_' in x),key=lambda x:int(x.rsplit('_',1)[-1].split('.')[0]))
  assert len(names)==10,names
  for file_id,name in enumerate(names):
   with z.open(name) as f:
    a=np.loadtxt(f,delimiter=',',dtype='float64')
   assert a.shape[1]==13 and int(np.max(a[:,0]))<=999
   key=a[:,0].astype('int64')*100+a[:,2].astype('int64')
   begin=np.r_[0,1+np.where(np.diff(key)!=0)[0]];end=np.r_[begin[1:],len(a)]
   for b,e in zip(begin,end):
    c=a[b:e];year=int(c[0,0]);tc=int(c[0,2]);global_year=file_id*1000+year
    identity=file_id*1000000+year*100+tc
    valid=np.isfinite(c[:,5:10]).all(axis=1)&(c[:,7]>0)&(c[:,9]>0)&(c[:,8]>0)
    if valid.sum()<2 or not valid.all() or not np.all(np.diff(c[:,3])==1):yield identity,global_year,None;continue
    lat=c[:,5];lon=c[:,6]-360
    if not near(lat,lon):yield identity,global_year,None;continue
    yield identity,global_year,(lat,lon,c[:,7],c[:,9]/1.852,c[:,8]*1.11,3)
   print('READ_FILE',file_id,len(begin),flush=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--catalog',choices=('raft','storm'),required=True);ap.add_argument('--limit',type=int,default=0);ap.add_argument('--batch',type=int,default=1000);args=ap.parse_args()
 out=ROOT/('pilot_results_v3' if args.limit else 'results_v3');out.mkdir(exist_ok=True);counts=dict(raw=0,selected=0,invalid=0,failed=0);ids=[];years=[];p=[];q=[];errors=[];t0=time.time()
 def save():
  if not ids:return
  dest=out/f'{args.catalog}_{counts["raw"]:06d}.npz'
  if dest.exists():raise FileExistsError(dest)
  np.savez_compressed(dest,ids=np.array(ids,dtype='int64'),years=np.array(years,dtype='int32'),peaks=np.array(p,dtype='float32'),ratios=np.array(q,dtype='float32'))
  print('SAVED',dest.name,'selected',counts['selected'],'raw',counts['raw'],'invalid',counts['invalid'],'failed',counts['failed'],'wall',round(time.time()-t0,1),flush=True)
  ids.clear();years.clear();p.clear();q.clear()
 generator=((i,i//15,x) for i,x in raft()) if args.catalog=='raft' else storm()
 for identity,year,track in generator:
  counts['raw']+=1
  if track is None:counts['invalid']+=1;continue
  try:
   ds=make_track(*track,source=args.catalog)
   pred=predict(ds);peaks=np.stack([x[0] for x in pred]);ratios=np.stack([x[1] for x in pred])
  except Exception as ex:
   counts['failed']+=1
   if len(errors)<20:errors.append((identity,str(ex)))
   continue
  counts['selected']+=1;ids.append(identity);years.append(year);p.append(peaks);q.append(ratios)
  if len(ids)>=args.batch:save()
  if args.limit and counts['selected']>=args.limit:break
 save()
 import json
 marker=out/f'{args.catalog}_{"pilot" if args.limit else "complete"}.json'
 if marker.exists():raise FileExistsError(marker)
 marker.write_text(json.dumps(dict(counts=counts,wall_seconds=round(time.time()-t0,2),errors=errors,catalog=args.catalog,limit=args.limit),indent=2))
 print('DONE',marker.read_text(),flush=True)
if __name__=='__main__':main()
