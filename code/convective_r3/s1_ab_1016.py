"""S1(a,b): HRRR FX native levels versus business gust, historical V1 cohort; NO AI scoring."""
import csv,datetime as dt,json,math,pathlib,traceback
import numpy as np
from earth2studio.data import HRRR,HRRR_FX
R=pathlib.Path('/content'); events=[x for x in csv.DictReader((R/'events_r2_verified.csv').open()) if x['group']=='v1'][:10]
levels=list(range(1,21));sparse=[*range(1,12),13,15,20]
vars=['u10m','v10m','fg10m']+[f'{v}{k}hl' for v in ('u','v','t','q','Z','p') for k in levels]
fx=HRRR_FX(verbose=False);hrrr=HRRR(verbose=False)
lat,lon=HRRR.grid();lon=lon%360
out=R/'s1_ab_rows.jsonl';assert not out.exists(),'immutable rows; do not overwrite'
ratio_samples=[];formula_samples=[];fg_samples=[];rows=[]
def gust(V,terrain,index):
 # V: variable-name->(level, station-pixel); terrain and 10m wind (station-pixel).
 z=np.stack([V[f'Z{k}hl'] for k in index])-terrain[None,:]
 theta=np.stack([V[f't{k}hl']*(1000/V[f'p{k}hl'])**.286*(1+.61*V[f'q{k}hl']) for k in index])
 speed=np.stack([np.hypot(V[f'u{k}hl'],V[f'v{k}hl']) for k in index]);base=np.hypot(V['u10m'],V['v10m'])
 valid=np.isfinite(theta)&np.isfinite(speed)&np.isfinite(z)&(z>=0)&np.isfinite(base[None,:]);cross=(theta>=theta[0:1]+.5)&valid
 first=np.where(cross.any(axis=0),cross.argmax(axis=0),len(index)-1)
 below=(np.arange(len(index))[:,None]<=first[None,:])&valid
 excess=np.maximum(0,np.where(below,np.clip(1-.5*z/1000,.5,1)*(speed-base[None,:]),-np.inf)).max(axis=0)
 result=base+excess;result[~np.isfinite(base)|~valid[0]]=np.nan
 return result,dict(z1_min=float(np.nanmin(z[0])),z1_max=float(np.nanmax(z[0])),nan_count=int((~np.isfinite(result)).sum()),pbl_fraction=float(cross.any(axis=0).mean()),pbl_capped=int((~cross.any(axis=0)).sum()),column_count=len(first))
for idx,e in enumerate(events,1):
 peak=dt.datetime.fromisoformat(e['utc']);center=(peak+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0);init=center-dt.timedelta(hours=2)
 hrs=[h for h in (1,2,3) if abs((init+dt.timedelta(hours=h)-peak).total_seconds())<=3600]
 a=np.sin((np.deg2rad(lat)-math.radians(float(e['lat'])))/2)**2+np.cos(np.deg2rad(lat))*math.cos(math.radians(float(e['lat'])))*np.sin((np.deg2rad(lon)-math.radians(float(e['lon'])%360))/2)**2
 yy,xx=np.where(12742*np.arcsin(np.sqrt(np.minimum(a,1)))<=25);assert len(yy)>0
 terrain=hrrr([init],['z']).sel(variable='z').values[0,yy,xx]
 pred=fx([init],[dt.timedelta(hours=h) for h in hrs],vars)
 fglist=[];full=[];sub=[];diagnostics=[]
 for j,h in enumerate(hrs):
  fields={name:pred.sel(variable=name).values[0,j,yy,xx] for name in vars}
  zfull,d=gust(fields,terrain,levels);zsub,sd=gust(fields,terrain,sparse);fg=fields['fg10m']
  ok=np.isfinite(zfull)&np.isfinite(zsub)&np.isfinite(fg)&(fg>0);assert ok.all(),('NaN',e['id'],h,d,sd)
  fglist.extend(fg.tolist());full.extend(zfull.tolist());sub.extend(zsub.tolist());diagnostics.append(d)
  del fields
 fv=np.asarray(full);gv=np.asarray(fglist);sv=np.asarray(sub);ratio_samples.extend((fv/gv).tolist());formula_samples.extend(fv.tolist());fg_samples.extend(gv.tolist())
 row=dict(id=e['id'],station=e['station'],peak_utc=e['utc'],init=init.isoformat(),hrs=hrs,n_grid=len(yy),n_points=len(fv),formula_fg_median_ratio=float(np.median(fv/gv)),formula_fg_peak_ratio=float(fv.max()/gv.max()),sparse_full_peak_ratio=float(sv.max()/fv.max()),formula_peak_ms=float(fv.max()),fg_peak_ms=float(gv.max()),sparse_peak_ms=float(sv.max()),diagnostics=diagnostics)
 with out.open('a') as f:f.write(json.dumps(row)+'\n')
 rows.append(row);print('EVENT',idx,row['id'],row['formula_fg_peak_ratio'],row['sparse_full_peak_ratio'],flush=True)
 del pred
assert len(rows)==10
metrics=dict(n_events=10,n_points=len(ratio_samples),median_ratio=float(np.median(ratio_samples)),pearson_r=float(np.corrcoef(formula_samples,fg_samples)[0,1]),sparse_full_peak_median_ratio=float(np.median([x['sparse_full_peak_ratio'] for x in rows])),a_pass=None,b_status=None)
metrics['a_pass']=.85<=metrics['median_ratio']<=1.15 and metrics['pearson_r']>=.8
b=metrics['sparse_full_peak_median_ratio'];metrics['b_status']='pass' if b>=.9 else 'limitation' if b>=.85 else 'fail'
(R/'s1_ab_metrics.json').write_text(json.dumps(metrics,indent=2));print('DONE',metrics,flush=True)
