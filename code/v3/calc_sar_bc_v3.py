#!/usr/bin/env python3
"""CyclObs SAR 3-km annular structure; R23.3 read_field adaptation (45–72).
Runs only in disposable Colab VM; source NC never downloaded to 工作站.
"""
import json, pathlib, requests, hashlib, math, numpy as np, xarray as xr
from datetime import datetime, timezone
ROOT=pathlib.Path('/content/L26_18_v3'); ROWS=json.loads((ROOT/'target_meta.json').read_text())
N=36

def dist(lat,lon,la,lo):
 a,b=np.deg2rad(lat),np.deg2rad(la)
 q=np.sin((b-a)/2)**2+np.cos(a)*np.cos(b)*np.sin(np.deg2rad(lo-lon)/2)**2
 return 12742*np.arcsin(np.sqrt(np.clip(q,0,1)))

def geometry(lat,lon,la,lo):
 rad=dist(lat[:,None],lon[None,:],la,lo)
 east=(lon[None,:]-lo)*np.cos(np.deg2rad(la))
 north=lat[:,None]-la
 sector=(np.floor((np.rad2deg(np.arctan2(east,north))%360)/10).astype(int))
 return rad,sector

def profile(w,valid,lat,lon,la,lo,coverage_only=False):
 rad,sec=geometry(lat,lon,la,lo); bins=np.floor(rad/3).astype(int)
 mask=(rad<=200)&(bins<67)&valid
 counts=np.bincount(bins[mask],minlength=67)
 sums=np.bincount(bins[mask],weights=w[mask],minlength=67)
 means=np.divide(sums,counts,out=np.full(67,np.nan),where=counts>0)
 sector_counts=np.bincount((bins[mask]*36+sec[mask]),minlength=67*36).reshape(67,36)
 coverage=(sector_counts>0).sum(axis=1)/36
 def winner(m):
  if np.isfinite(m).any():return int(np.nanargmax(m))
  return None
 ka=winner(means); kb=winner(np.where(coverage>=.8,means,np.nan))
 edge=min(float(np.min(dist(lat[0],lon,la,lo))),float(np.min(dist(lat[-1],lon,la,lo))),float(np.min(dist(lat,lon[0],la,lo))),float(np.min(dist(lat,lon[-1],la,lo))))
 out={'rmw_km':3*(ka+.5) if ka is not None else None,'rmw_80_km':3*(kb+.5) if kb is not None else None,'winning_mean_ms':float(means[ka]) if ka is not None else None,'winning_count':int(counts[ka]) if ka is not None else 0,'edge_km':edge,'winning_ring_truncated':edge<3*(ka+1) if ka is not None else None,'winning_ring_coverage':float(coverage[ka]) if ka is not None else None}
 if coverage_only or ka is None:return out
 rmax=out['rmw_km']; band=mask&(rad<=2*rmax)
 out['coverage_0_2rmw']=float(np.unique(sec[band]).size/36)
 inner=mask&(rad>=.5*rmax)&(rad<1.5*rmax)
 cs=np.bincount(sec[inner],minlength=36); sm=np.bincount(sec[inner],weights=w[inner],minlength=36)
 sector_means=np.divide(sm,cs,out=np.full(36,np.nan),where=cs>0)
 good=np.isfinite(sector_means); theta=np.deg2rad(np.arange(36)*10+5)
 if good.sum()>=10:
  co=np.stack([np.ones(good.sum()),np.cos(theta[good]),np.sin(theta[good])],axis=1)
  m,a,b=np.linalg.lstsq(co,sector_means[good],rcond=None)[0]
  out['wave1_fraction']=float(np.hypot(a,b)/m) if m>0 else None
  out['wave1_peak_deg_north_cw']=float(np.rad2deg(np.arctan2(b,a))%360)
 else:out['wave1_fraction']=out['wave1_peak_deg_north_cw']=None
 return out

def clean(x):
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.floating,)):return float(x)
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,(float,int,str,bool)) or x is None:return x
 return str(x)

results=[];attrs=[]
for idx,row in enumerate(ROWS):
 stamp=row['acquisition_start_time']; path=ROOT/f'sar_{idx:02d}.nc'
 if not path.exists():
  response=requests.get(row['data_url'],timeout=120);response.raise_for_status();path.write_bytes(response.content)
 ds=xr.open_dataset(path)
 w=np.asarray(ds['wind_speed'][0].values,dtype=float);q=np.asarray(ds['quality_level'][0].values,dtype=float);rej=np.asarray(ds['rejection_flag'][0].values,dtype=float)
 lat=np.asarray(ds['lat'].values);lon=np.asarray(ds['lon'].values)
 valid=np.isfinite(w)&(w>=0)&np.isfinite(q)&(q>=3)&np.isfinite(rej)&(rej==0)
 # Original product marks land, ice, coast, rain and bright target as rejected.
 center=row['eye_center'];out={'index':idx,'storm':row['cyclone_name'],'time_utc':stamp,'mission':row['mission'],'data_url':row['data_url'],'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'grid_shape':list(w.shape),'grid_step_km':[float(abs(np.median(np.diff(lat)))*111.2),float(abs(np.median(np.diff(lon)))*111.2*np.cos(np.deg2rad(np.mean(lat))))],'center_source':'CyclObs TCVA eye_center' if center else 'CyclObs eye_center missing; no ATCF fallback used','center_quality_flag_api':row['analysis_center_quality_flag'],'analysis_rmax_km':float(row['analysis_rmax'])/1000 if row['analysis_rmax'] else None,'track_source_api':row['track_source'],'valid_fraction':float(valid.mean())}
 if center:
  lo,la=map(float,center.replace('POINT (','').replace(')','').split());out['center_lat_lon']=[la,lo]
  main=profile(w,valid,lat,lon,la,lo);out.update(main)
  shift=[]
  for dj,di in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
   j=int(np.argmin(abs(lat-la)));i=int(np.argmin(abs(lon-lo)))
   j2=np.clip(j+dj,0,len(lat)-1);i2=np.clip(i+di,0,len(lon)-1)
   zz=profile(w,valid,lat,lon,float(lat[j2]),float(lon[i2]),True)
   shift.append({'dj':dj,'di':di,'rmw_km':zz['rmw_km'],'relative_change':abs(zz['rmw_km']-main['rmw_km'])/main['rmw_km'] if zz['rmw_km'] is not None else None})
  out['shift_8']=shift
  out['rmw_80_relative_change']=abs(main['rmw_80_km']-main['rmw_km'])/main['rmw_km'] if main['rmw_80_km'] is not None else None
  out['rmax_relative_change']=abs(out['analysis_rmax_km']-main['rmw_km'])/main['rmw_km'] if out['analysis_rmax_km'] is not None else None
  changes=[x['relative_change'] for x in shift]+[out['rmw_80_relative_change'],out['rmax_relative_change']]
  out['max_relative_change']=max(x for x in changes if x is not None)
 else:out['center_lat_lon']=None;out['rmw_km']=None;out['max_relative_change']=None
 if idx in (0,6):
  attrs.append({'index':idx,'time':stamp,'global':{k:clean(v) for k,v in ds.attrs.items()},'variables':{k:{'attrs':{a:clean(v) for a,v in ds[k].attrs.items()},'shape':list(ds[k].shape)} for k in ('wind_speed','quality_level','rejection_flag','heterogeneity_mask','time','lat','lon')},'grid_step_km':out['grid_step_km'],'api_center_fields':{k:row[k] for k in ('eye_center','analysis_center_quality_flag','analysis_rmax','track_source','track_point','rmw')}})
 ds.close();results.append(out);(ROOT/'sar_results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
 print('SAR_PROGRESS',idx+1,len(ROWS),stamp,'center',out['center_source'],'rmw',out['rmw_km'],'size',path.stat().st_size,flush=True)
(ROOT/'nc_attributes.json').write_text(json.dumps(attrs,indent=2,ensure_ascii=False));print('SAR_DONE',len(results),'main',sum(x['rmw_km'] is not None for x in results),'median',float(np.median([x['max_relative_change'] for x in results if x['max_relative_change'] is not None])),flush=True)
