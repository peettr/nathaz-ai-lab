"""Post-registration sensitivity: ERA5 6-h times without station convective marks."""
import json,csv,io,datetime as dt,calendar,time
from pathlib import Path
import numpy as np,xarray as xr
from run_colab import ROOT,STATIONS,GRID,query,fetch,parse,convcode
meta=json.loads((ROOT/'era_grid.json').read_text());i0,i1,j0,j1=meta['crop'];sts=meta['stations'];url=meta['source_url']
s=xr.open_zarr(url,storage_options={'token':'anon'},consolidated=True).isel(latitude=slice(None,None,-1));slat=s.latitude.values;slon=s.longitude.values
mlat=np.sort(np.rad2deg(np.arcsin(np.polynomial.legendre.leggauss(180)[0])));mlon=np.arange(360)+.5
def edges(x,periodic=False):
 e=np.empty(len(x)+1);e[1:-1]=(x[1:]+x[:-1])/2;e[0]=x[0]-(x[1]-x[0])/2;e[-1]=x[-1]+(x[-1]-x[-2])/2
 if not periodic:e[0]=max(-90,e[0]);e[-1]=min(90,e[-1])
 return e
sy=edges(slat);sx=edges(slon,True);ty=edges(mlat);tx=edges(mlon,True)
W=[]
for st in sts:
 i,j=GRID[st]
 yy=np.maximum(0,np.sin(np.deg2rad(np.minimum(sy[i0+1:i1+1],ty[i+1])))-np.sin(np.deg2rad(np.maximum(sy[i0:i1],ty[i]))))
 xx=np.maximum(0,np.minimum(sx[j0+1:j1+1],tx[j+1])-np.maximum(sx[j0:j1],tx[j]))
 w=yy[:,None]*xx[None,:];w/=w.sum();W.append(w.ravel())
W=np.stack(W,axis=1);assert np.allclose(W.sum(axis=0),1)
sevents=[r for r in json.loads((ROOT/'storms.json').read_text()) if r['type'] in ('Thunderstorm Wind','Tornado','Hail')]
from collections import defaultdict
SE=defaultdict(list)
for r in sevents:SE[r['station']].append((parse(r['start']),parse(r['end'])))
out=ROOT/'era_noconv.jsonl';done=set()
if out.exists():
 for z in out.read_text().splitlines():done.add(json.loads(z)['season_year'])
for year in range(2007,2022):
 if year in done:continue
 t0=time.monotonic();a=dt.datetime(year,10,1);b=dt.datetime(year+1,4,1)
 bad={}
 for st in STATIONS:
  with fetch(query(st,a-dt.timedelta(hours=1),b+dt.timedelta(hours=1))) as resp:
   rr=list(csv.DictReader(io.TextIOWrapper(resp,encoding='utf8',errors='replace')))
  bad[st]=[parse(r.get('valid','')) for r in rr if convcode(r.get('metar',''),r.get('wxcodes','')) and parse(r.get('valid',''))]
  print('MARKS',year,st,len(bad[st]),flush=True)
 extrema={st:None for st in STATIONS};counts={st:0 for st in STATIONS};excluded={st:0 for st in STATIONS}
 for m in (10,11,12,1,2,3):
  yr=year if m>=10 else year+1
  batch=s[['10m_u_component_of_wind','10m_v_component_of_wind']].sel(time=slice(f'{yr}-{m:02d}-01',f'{yr}-{m:02d}-{calendar.monthrange(yr,m)[1]:02d}T23:59')).isel(latitude=slice(i0,i1),longitude=slice(j0,j1)).load()
  n=len(batch.time);u=batch['10m_u_component_of_wind'].values.reshape(n,-1)@W;v=batch['10m_v_component_of_wind'].values.reshape(n,-1)@W;speed=np.hypot(u,v)
  for k,ts in enumerate(batch.time.values):
   t=dt.datetime.fromisoformat(str(ts)[:19]);
   for st in STATIONS:
    if any(abs((x-t).total_seconds())<=3600 for x in bad[st]) or any(z0-dt.timedelta(hours=1)<=t<=z1+dt.timedelta(hours=1) for z0,z1 in SE[st] if z0.year in (year,year+1)):
     excluded[st]+=1;continue
    val=float(speed[k,sts.index(st)]);counts[st]+=1
    if extrema[st] is None or val>extrema[st]:extrema[st]=val
  print('NOCONV_MONTH',year,m,round(time.monotonic()-t0,1),flush=True)
 row={'season_year':year,'stations':{st:{'ace1_max_mps':extrema[st],'included_6h':counts[st],'excluded_6h':excluded[st]} for st in STATIONS}}
 with out.open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
 print('NOCONV_DONE',year,round(time.monotonic()-t0,1),flush=True)
(ROOT/'era_noconv.done').write_text(json.dumps({'seasons':sum(1 for _ in out.open()),'expected':15}))
