"""S1 a/b: all 50 native wrfnat hybrid levels versus fixed StormCast 14 levels; seen V1 cases only."""
import csv,datetime as dt,json,math,pathlib,time
import numpy as np
from loguru import logger
from earth2studio.data import HRRR,HRRR_FX
from earth2studio.lexicon.hrrr import HRRRFXLexicon
logger.remove()
R=pathlib.Path('/content'); events=[x for x in csv.DictReader((R/'events_r2_verified.csv').open()) if x['group']=='v1'][:10]
levels=list(range(1,51));sparse=[*range(1,12),13,15,20]
assert len(levels)==50 and len(sparse)==14
for v in ('u','v','t','q','Z','p'):
 assert all(HRRRFXLexicon.VOCAB[f'{v}{k}hl'].startswith('wrfnat::') for k in levels)
fx=HRRR_FX(verbose=False);hrrr=HRRR(verbose=False);lat,lon=HRRR.grid();out=R/'s1_ab_full_rows.jsonl'
if out.exists():
 rows=[json.loads(x) for x in out.read_text().splitlines() if x.strip()]
 assert [x['id'] for x in rows]==[e['id'] for e in events[:len(rows)]]
else: rows=[]
# All finite comparisons; equation PBL search from lowest layer with virtual-potential-temperature offset.
def gust(fields,terrain,ix):
 z=fields['Z'][ix]-terrain[None,:]
 theta=fields['t'][ix]*(1000/fields['p'][ix])**.286*(1+.61*fields['q'][ix])
 speed=np.hypot(fields['u'][ix],fields['v'][ix]);base=np.hypot(fields['u10m'],fields['v10m'])
 valid=np.isfinite(theta)&np.isfinite(speed)&np.isfinite(z)&(z>=0)&np.isfinite(base[None,:])
 cross=(theta>=theta[0:1]+.5)&valid
 first=np.where(cross.any(axis=0),cross.argmax(axis=0),len(ix)-1)
 below=(np.arange(len(ix))[:,None]<=first[None,:])&valid
 excess=np.where(below,np.clip(1-.5*z/1000,.5,1)*(speed-base[None,:]),-np.inf)
 result=base+np.maximum(0,np.max(excess,axis=0));result[~np.isfinite(base)|~valid[0]]=np.nan
 return result,dict(z1_min=float(np.nanmin(z[0])),z1_max=float(np.nanmax(z[0])),nan_count=int((~np.isfinite(result)).sum()),pbl_fraction=float(cross.any(axis=0).mean()),pbl_capped=int((~cross.any(axis=0)).sum()))
for idx,e in enumerate(events[len(rows):],len(rows)+1):
 t0=time.monotonic();peak=dt.datetime.fromisoformat(e['utc']);center=(peak+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0);init=center-dt.timedelta(hours=2)
 hrs=[h for h in (1,2,3) if abs((init+dt.timedelta(hours=h)-peak).total_seconds())<=3600]
 a=np.sin((np.deg2rad(lat)-math.radians(float(e['lat'])))/2)**2+np.cos(np.deg2rad(lat))*math.cos(math.radians(float(e['lat'])))*np.sin((np.deg2rad(lon)-math.radians(float(e['lon'])))/2)**2
 yy,xx=np.where(12742*np.arcsin(np.sqrt(np.minimum(a,1)))<=25);assert len(yy)>0
 terrain=hrrr([init],['z']).sel(variable='z').values[0,yy,xx]/9.80665 # Earth2Studio z is geopotential m2/s2; native HGT is m
 fv=[];gv=[];sv=[];diag=[]
 for h in hrs:
  fields={};lead=[dt.timedelta(hours=h)]
  raw=fx([init],lead,['u10m','v10m','fg10m']);pts=raw.values[0,0,:,yy,xx];fields.update(zip(['u10m','v10m','fg10m'],pts.T));del raw,pts
  for v in ('u','v','t','q','Z','p'):
   block=[f'{v}{k}hl' for k in levels];raw=fx([init],lead,block);pts=raw.values[0,0,:,yy,xx];assert pts.shape==(len(yy),50),pts.shape
   fields[v]=pts.T.copy();del raw,pts
   print('FETCH',idx,h,v,round(time.monotonic()-t0,1),flush=True)
  full,d=gust(fields,terrain,np.arange(50));sub,sd=gust(fields,terrain,np.array(sparse)-1);fg=fields['fg10m']
  ok=np.isfinite(full)&np.isfinite(sub)&np.isfinite(fg)&(fg>0);assert ok.all(),('missing',e['id'],h,d,sd)
  fv.extend(full.tolist());sv.extend(sub.tolist());gv.extend(fg.tolist());diag.append(d)
  del fields
 f=np.asarray(fv);g=np.asarray(gv);s=np.asarray(sv)
 row=dict(id=e['id'],station=e['station'],peak_utc=e['utc'],init=init.isoformat(),hrs=hrs,n_grid=len(yy),n_points=len(f),formula_fg_median_ratio=float(np.median(f/g)),formula_fg_peak_ratio=float(f.max()/g.max()),sparse_full_peak_ratio=float(s.max()/f.max()),formula_peak_ms=float(f.max()),fg_peak_ms=float(g.max()),sparse_peak_ms=float(s.max()),diagnostics=diag,formula_samples=fv,fg_samples=gv,wall_s=round(time.monotonic()-t0,1),source='HRRRFXLexicon wrfnat 50 native levels')
 with out.open('a') as stream: stream.write(json.dumps(row)+'\n')
 rows.append(row);print('EVENT',idx,row['id'],row['formula_fg_peak_ratio'],row['sparse_full_peak_ratio'],row['wall_s'],flush=True)
assert len(rows)==10
f=np.concatenate([np.array(x['formula_samples']) for x in rows]);g=np.concatenate([np.array(x['fg_samples']) for x in rows]);r=np.concatenate([np.array(x['formula_samples'])/np.array(x['fg_samples']) for x in rows])
metrics=dict(n_events=10,n_points=len(r),median_ratio=float(np.median(r)),pearson_r=float(np.corrcoef(f,g)[0,1]),sparse_full_peak_median_ratio=float(np.median([x['sparse_full_peak_ratio'] for x in rows])))
metrics['a_pass']=.85<=metrics['median_ratio']<=1.15 and metrics['pearson_r']>=.8
b=metrics['sparse_full_peak_median_ratio'];metrics['b_status']='pass' if b>=.9 else 'limitation' if b>=.85 else 'fail'
(R/'s1_ab_full_metrics.json').write_text(json.dumps(metrics,indent=2));print('DONE',metrics,flush=True)
