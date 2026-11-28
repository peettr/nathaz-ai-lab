"""Supplement: unchanged regional gates plus new station-neighborhood fields."""
import json,math,csv,os
from pathlib import Path
import numpy as np,xarray as xr
import metpy.calc as mp
from metpy.units import units
R=Path('/content/ai_weather')
source=Path('/content/ai_weather_metrics.py').read_text().split("all_results={'definition':")[0]
exec(compile(source,'metrics_prefix.py','exec'))
KEY['E3']=KEY['E1'];POINT['E3']=(34.5872,-99.3381)
OLD=json.loads(Path('/content/ai_weather/old_metrics.json').read_text())
RESULT={'definition':OLD['definition'],'cases':[],'reference':{},'baseline':{},'supplementary_37':{}}
FIELD=['SBCAPE_Jkg','SBCIN_Jkg','MUCAPE_Jkg','DCAPE_Jkg','shear01_ms','shear03_ms','shear06_ms','RH03_percent','lapse700_500_Kkm','surface_T_K','surface_Td_K']
rows=[]
def file_truth(e,tag):
 d=np.load(R/f'truth_{e}_{tag}_supp{"_gridfix" if e=="E3" else ""}.npz');return {k:d[k] for k in d.files}
def file_model(m,e,h):
 suffix='supp_rhproxy' if m=='FuXi' else 'supp'
 ds=xr.open_zarr(R/f'{m}_{e}_{h}_{suffix}.zarr',consolidated=False)
 d={'lat':ds.lat.values,'lon':ds.lon.values}
 for v in ds.data_vars:
  try:d[v]=ds[v].isel(time=0,lead_time=-1).values
  except Exception:continue
 return d
def at_grid(d,kind,full,terrain,i,j):
 out={v:None for v in FIELD};out['surface_T_K']=float(d['t2m'][i,j]);out['surface_Td_K']=float(d['d2m'][i,j]) if 'd2m' in d else None;out['Td_method']='ERA5_2m' if 'd2m' in d else 'proxy_lowest_above_ground_q_to_2m'
 lev,a,s=build_profiles(d,(i,j),kind,full,terrain)
 if out['surface_Td_K'] is None:
  try:
   if isinstance(a['q'],tuple): q0=mp.specific_humidity_from_dewpoint(lev[0]*units.hPa,mp.dewpoint_from_relative_humidity(a['t'][0]*units.kelvin,np.clip(a['q'][1][0],.1,100)/100)).m
   else:q0=float(a['q'][0])
   out['surface_Td_K']=float(mp.dewpoint_from_specific_humidity((s['sp']/100 if np.isfinite(s['sp']) else lev[0])*units.hPa,s['t2m']*units.kelvin,np.clip(q0,1e-8,.1)*units.dimensionless).to('kelvin').m)
  except Exception:pass
 p=lev*units.hPa;t=a['t']*units.kelvin
 if isinstance(a['q'],tuple): td=mp.dewpoint_from_relative_humidity(t,np.clip(a['q'][1],.1,100)/100)
 else:td=mp.dewpoint_from_specific_humidity(p,t,np.clip(a['q'],1e-8,.1)*units.dimensionless)
 h=np.array(a['z'])/9.80665-s['zsfc']/9.80665
 if len(p)<6 or not np.all(np.isfinite(td.m)) or not np.all(np.diff(h)>0):return out
 def attempt(k,fn):
  try:
   v=float(fn());out[k]=v if np.isfinite(v) else None
  except Exception:pass
 attempt('SBCAPE_Jkg',lambda:max(0,mp.surface_based_cape_cin(p,t,td)[0].to('joule/kilogram').m))
 attempt('SBCIN_Jkg',lambda:min(0,mp.surface_based_cape_cin(p,t,td)[1].to('joule/kilogram').m))
 attempt('MUCAPE_Jkg',lambda:max(0,mp.most_unstable_cape_cin(p,t,td)[0].to('joule/kilogram').m))
 attempt('DCAPE_Jkg',lambda:max(0,mp.downdraft_cape(p,t,td)[0].to('joule/kilogram').m))
 hh=np.r_[10.,h];uu=np.r_[s['u10m'],a['u']];vv=np.r_[s['v10m'],a['v']];pp=np.r_[s['sp']/100 if np.isfinite(s['sp']) else max(lev)+2,lev]*units.hPa
 for key,depth in [('shear01_ms',1000),('shear03_ms',3000),('shear06_ms',6000)]:
  if hh[-1]>=depth+10:
   attempt(key,lambda depth=depth: mp.wind_speed(*mp.bulk_shear(pp,uu*units('m/s'),vv*units('m/s'),height=hh*units.meter,bottom=10*units.meter,depth=depth*units.meter)).to('m/s').m)
 if min(lev)<=500 and max(lev)>=700:
  z700=np.interp(700,lev[::-1],h[::-1]);z500=np.interp(500,lev[::-1],h[::-1]);t700=np.interp(700,lev[::-1],a['t'][::-1]);t500=np.interp(500,lev[::-1],a['t'][::-1]);out['lapse700_500_Kkm']=float((t700-t500)/(z500-z700)*1000)
 rh=mp.relative_humidity_from_dewpoint(t,td).m*100
 good=(h<=3000)&np.isfinite(rh)
 if good.sum()>=2:
  hz=h[good];rv=rh[good];top=min(3000,hz[-1])
  if top>hz[0]:out['RH03_percent']=float(np.trapezoid(np.r_[rv,np.interp(top,h, rh)][:-1] if False else np.r_[rv[:np.searchsorted(hz,top,side='right')],np.interp(top,hz,rv)],np.r_[hz[:np.searchsorted(hz,top,side='right')],top])/(top-hz[0]))
 return out

def station_rows(d,e,kind,full=False,terrain=None,lead=None):
 la=np.asarray(d['lat']);lo=np.asarray(d['lon']);slat,slon=POINT[e]
 ci=int(np.argmin(abs(la-slat)));cj=int(np.argmin(abs(lo-(slon%360))))
 assert ci>0 and cj>0 and ci<len(la)-1 and cj<len(lo)-1,(e,ci,cj,la,lo)
 for i in range(ci-1,ci+2):
  for j in range(cj-1,cj+2):
   rec=dict(event=e,source=kind,lead_h=lead if lead is not None else '',vertical_levels=37 if full else 13,site_lat=slat,site_lon=slon,grid_lat=float(la[i]),grid_lon=float(lo[j]-360),row_offset=i-ci,col_offset=j-cj,is_station_grid=(i==ci and j==cj),RH03_lower_limit_m=None)
   try:
    lev,a,s=build_profiles(d,(i,j),kind if kind in ('Pangu6','FuXi') else 'truth',full,terrain)
    rec['RH03_lower_limit_m']=float(min(a['z'])/9.80665-s['zsfc']/9.80665)
    rec.update(at_grid(d,kind if kind in ('Pangu6','FuXi') else 'truth',full,terrain,i,j))
   except Exception as ex:rec.update({v:None for v in FIELD});rec['error']=str(ex)
   rows.append(rec)
for e in ('E1','E2','E3'):
 CURRENT_EVENT=e
 truth=file_truth(e,'valid');terrain=truth['zsfc']
 # Recomputed E1/E2 13-/37-level truth solely for station CSV; immutable prior verdicts retained.
 station_rows(truth,e,'ERA5',terrain=terrain);station_rows(truth,e,'ERA5',full=True,terrain=terrain)
 if e!='E3':continue
 main=indices(truth,'truth');RESULT['reference'][e]=main
 RESULT['supplementary_37'][e]=indices(truth,'truth',full=True)
 for lag in (24,48,72,120):RESULT['baseline'][f'E3_P{lag}']=indices(file_truth(e,f'P{lag}'),'truth')
for m in ('Pangu6','FuXi'):
 for e in ('E1','E2','E3'):
  CURRENT_EVENT=e;terrain=file_truth(e,'valid')['zsfc']
  for h in (12,24,48,72,120):
   d=file_model(m,e,h);station_rows(d,e,m,terrain=terrain,lead=h)
   if e=='E3':
    summary=indices(d,m,terrain=terrain);tag=f'P{24*math.ceil(h/24)}'
    RESULT['cases'].append(dict(event=e,model=m,lead_h=h,summary=summary,baseline_tag=tag,judge=judge(e,summary,RESULT['reference'][e],RESULT['baseline'][f'E3_{tag}'])))
    print('JUDGE',e,m,h,RESULT['cases'][-1]['judge'],flush=True)
  print('CSV_STEP',m,e,len(rows),flush=True)
assert len(rows)==324 and len(RESULT['cases'])==10,(len(rows),len(RESULT['cases']))
with (R/'station_parameters_supp.csv').open('x',newline='') as f:
 fields=list(dict.fromkeys(k for row in rows for k in row));w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
(R/'metrics_E3_supp.json').write_text(json.dumps(RESULT,indent=2,allow_nan=False))
print('SUPP_METRICS_COMPLETE',len(RESULT['cases']),len(rows),flush=True)
