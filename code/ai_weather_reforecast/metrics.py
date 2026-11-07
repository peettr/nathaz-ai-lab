"""MetPy regional environmental indices and preregistered acceptance tests."""
import os,json,math,traceback,warnings
from datetime import datetime
import numpy as np, xarray as xr
import metpy.calc as mp
from metpy.units import units
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
warnings.filterwarnings('ignore',category=RuntimeWarning)
ROOT='/content/ai_weather'; LEVEL13=np.array([1000,925,850,700,600,500,400,300,250,200,150,100,50]); KEY={'E1':['MLCAPE','DCAPE','shear06'],'E2':['MUCAPE','shear06','inversion_K']}; POINT={'E1':(34.98426,-94.68778),'E2':(40.16,-103.21)}

def truth_file(e,tag):
 d=np.load(f'{ROOT}/truth_{e}_{tag}_v2.npz');return {k:d[k] for k in d.files}

def model_file(m,e,l):
 suffix=('grid25_rhproxy_v2' if (e,l)==('E1',12) else 'grid25_rhproxy_v3') if m=='FuXi' else 'grid25'
 ds=xr.open_zarr(f'{ROOT}/{m}_{e}_{l}_{suffix}.zarr', consolidated=False)
 d={'lat':ds.lat.values,'lon':ds.lon.values}
 for v in ds.data_vars:
  try:d[v]=ds[v].isel(time=0,lead_time=-1).values
  except Exception:continue
 return d

def build_profiles(d,ij,kind,full=False,terrain=None):
 i,j=ij
 if kind=='truth':
  lev=np.asarray(d['level']); a={v:np.asarray(d[v][:,i,j]) for v in ('t','q','u','v','z')}; s={v:float(d[v][i,j]) for v in ('t2m','u10m','v10m','sp','zsfc','tcwv')}
  if not full:
   idx=[np.where(lev==p)[0][0] for p in LEVEL13];lev=lev[idx];a={v:x[idx] for v,x in a.items()}
 else:
  lev=LEVEL13.copy();a={v:np.array([float(d[f'{v}{p}'][i,j]) for p in lev]) for v in ('t','u','v','z')}
  s={v:float(d[v][i,j]) for v in ('t2m','u10m','v10m')}
  s['zsfc']=float(terrain[i,j]);s['sp']=np.nan;s['tcwv']=np.nan
  if kind=='Pangu6':a['q']=np.array([float(d[f'q{p}'][i,j]) for p in lev])
  else:
   rh=np.array([float(d[f'r{p}'][i,j]) for p in lev]);a['q']=('RH',rh)
 # Filter underground using fixed observed surface geopotential; level height is geopotential height.
 keep=np.array(a['z'])>=s['zsfc']-1
 lev=lev[keep];a={k:(v[0],v[1][keep]) if isinstance(v,tuple) else v[keep] for k,v in a.items()}
 order=np.argsort(-lev);lev=lev[order];a={k:(v[0],v[1][order]) if isinstance(v,tuple) else v[order] for k,v in a.items()}
 return lev,a,s

def indices(d,kind,full=False,terrain=None):
 ny,nx=len(d['lat']),len(d['lon']); vals={k:np.full((ny,nx),np.nan) for k in ['MLCAPE','MUCAPE','DCAPE','shear06','shear01','lapse03','inversion_K','inversion_height_m','PW_mm']}; errors=[]
 for i in range(ny):
  for j in range(nx):
   try:
    lev,a,s=build_profiles(d,(i,j),kind,full,terrain)
    p=lev*units.hPa;t=a['t']*units.kelvin
    if isinstance(a['q'],tuple):td=mp.dewpoint_from_relative_humidity(t,np.clip(a['q'][1],0.1,100)/100)
    else:td=mp.dewpoint_from_specific_humidity(p,t,np.clip(a['q'],1e-8,.1)*units.dimensionless)
    z=np.array(a['z'])/9.80665; h=z-s['zsfc']/9.80665
    if len(p)<6 or not np.all(np.isfinite(td.m)) or not np.all(np.diff(h)>0):raise ValueError('invalid profile')
    for name,fn in [('MLCAPE',mp.mixed_layer_cape_cin),('MUCAPE',mp.most_unstable_cape_cin)]:
     try:vals[name][i,j]=max(0,float(fn(p,t,td)[0].to('joule/kilogram').m))
     except Exception as ex:errors.append(f'{kind} {i},{j} {name} {ex}')
    try:vals['DCAPE'][i,j]=max(0,float(mp.downdraft_cape(p,t,td)[0].to('joule/kilogram').m))
    except Exception as ex:errors.append(f'{kind} {i},{j} DCAPE {ex}')
    # MetPy bulk_shear with heights; 10-m anchor included for 0-1/0-6 km.
    hh=np.r_[10.,h]; uu=np.r_[s['u10m'],a['u']]; vv=np.r_[s['v10m'],a['v']]
    pp=np.r_[s['sp']/100 if np.isfinite(s['sp']) else max(lev)+2,lev]*units.hPa
    for key,depth in [('shear01',1000),('shear06',6000)]:
     if hh[-1]>=depth+10:
      su,sv=mp.bulk_shear(pp,uu*units('m/s'),vv*units('m/s'),height=hh*units.meter,bottom=10*units.meter,depth=depth*units.meter)
      vals[key][i,j]=float(mp.wind_speed(su,sv).m)
    if hh[-1]>=3010:vals['lapse03'][i,j]=(s['t2m']-np.interp(3010,hh,np.r_[s['t2m'],a['t']]))/3
    # Max contiguous positive temperature rise from the 2-m surface through 3 km AGL.
    tt=np.r_[s['t2m'],a['t']]; positive=np.diff(tt); mask=hh[1:]<=3000
    candidates=np.where(mask & (positive>0))[0]
    if len(candidates):k=candidates[np.argmax(positive[candidates])]; vals['inversion_K'][i,j]=positive[k];vals['inversion_height_m'][i,j]=hh[k+1]
    else:vals['inversion_K'][i,j]=0.;vals['inversion_height_m'][i,j]=np.nan
    q=a['q'] if not isinstance(a['q'],tuple) else mp.specific_humidity_from_dewpoint(p,td).m
    vals['PW_mm'][i,j]=float(mp.precipitable_water(p,td).to('millimeter').m)
   except Exception as ex:errors.append(f'{kind} {i},{j} profile {ex}')
 lat=np.array(d['lat']);lon=np.array(d['lon']);weights=np.cos(np.deg2rad(lat))[:,None]*np.ones((1,nx))
 summary={}
 for k,a in vals.items():
  if np.isfinite(a).any():
   summary[k]={'max':float(np.nanmax(a)),'mean':float(np.nansum(a*weights)/np.nansum(weights*np.isfinite(a))),'n_valid':int(np.isfinite(a).sum())}
  else:summary[k]={'max':None,'mean':None,'n_valid':0}
 peak=vals['MUCAPE']
 if np.isfinite(peak).any():
  ii,jj=np.unravel_index(np.nanargmax(peak),peak.shape);lat0,lon0=POINT[CURRENT_EVENT];phi1,phi2=np.radians([lat0,lat[ii]]);dlon=np.radians(((lon[jj]-360)-lon0));dphi=phi2-phi1
  km=6371*2*np.arcsin(np.sqrt(np.sin(dphi/2)**2+np.cos(phi1)*np.cos(phi2)*np.sin(dlon/2)**2))
  summary['MUCAPE_peak_location']={'lat':float(lat[ii]),'lon':float(lon[jj]-360),'distance_km':float(km)}
 summary['_errors']=errors[:20];summary['_error_count']=len(errors)
 return summary

def judge(e,forecast,ref,baseline):
 keys=KEY[e];abs_err={k:abs(forecast[k]['max']-ref[k]['max']) if forecast[k]['max'] is not None and ref[k]['max'] is not None else None for k in keys}
 base_err={k:abs(baseline[k]['max']-ref[k]['max']) if baseline[k]['max'] is not None and ref[k]['max'] is not None else None for k in keys}
 ok=[]
 for k in keys:
  err=abs_err[k];rv=ref[k]['max'];tol=5 if k=='shear06' else 2 if k=='inversion_K' else .25*abs(rv) if rv is not None else None
  ok.append(err is not None and tol is not None and err<=tol)
 criterion1=all(ok)
 mae_ai=float(np.mean(list(abs_err.values()))) if all(v is not None for v in abs_err.values()) else None
 mae_p=float(np.mean(list(base_err.values()))) if all(v is not None for v in base_err.values()) else None
 criterion2=mae_ai is not None and mae_p is not None and mae_ai<=.7*mae_p
 dist=forecast.get('MUCAPE_peak_location',{}).get('distance_km')
 criterion3=dist is not None and dist<=150
 return dict(c1=bool(criterion1),c1_by_parameter=dict(zip(keys,map(bool,ok))),c2=bool(criterion2),c3=bool(criterion3),pass_all=bool(criterion1 and criterion2 and criterion3),absolute_error=abs_err,baseline_absolute_error=base_err,mae_ai=mae_ai,mae_p=mae_p,distance_km=dist)

all_results={'definition':{'reference':'ERA5 ARCO public 13 pressure levels (37-level supplementary)','MLCAPE':'MetPy mixed_layer_cape_cin default 100 hPa layer from first above-terrain isobaric level','MUCAPE':'MetPy most_unstable_cape_cin default 300 hPa depth','DCAPE':'MetPy downdraft_cape lowest theta-e parcel 700–500 hPa','shear':'MetPy bulk_shear 10-m winds to 1 or 6 km AGL','inversion':'largest adjacent positive T increase from 2m to any above-terrain isobaric level <=3 km AGL; upper height reported','criterion2':'unweighted arithmetic mean of absolute region-max errors across three named parameters, literal predetermined wording; mixed units caveat','persistence':'ERA5 at valid minus 24*ceil(L/24) h','terrain':'static observed ERA5 surface geopotential for pressure-level underground masking'},'cases':[],'reference':{},'baseline':{},'supplementary_37':{}}
for e in ('E1','E2'):
 CURRENT_EVENT=e
 ref=truth_file(e,'valid'); terrain=ref['zsfc']; main=indices(ref,'truth');all_results['reference'][e]=main
 print('REFERENCE_DEBUG',e,{k:main[k]['max'] for k in KEY[e]},main['_errors'][:3],flush=True)
 full=indices(ref,'truth',full=True);all_results['supplementary_37'][e]=full
 for lag in (24,48,72,120):
  tag='P'+str(lag);all_results['baseline'][f'{e}_{tag}']=indices(truth_file(e,tag),'truth')
 for m in ('Pangu6','FuXi'):
  for l in (12,24,48,72,120):
   tag='P'+str(int(math.ceil(l/24)*24)); baseline=all_results['baseline'][f'{e}_{tag}']
   suffix=('grid25_rhproxy_v2' if (e,l)==('E1',12) else 'grid25_rhproxy_v3') if m=='FuXi' else 'grid25'
   path=f'{ROOT}/{m}_{e}_{l}_{suffix}.json'
   if not os.path.exists(path):all_results['cases'].append(dict(event=e,model=m,lead_h=l,error='forecast missing'));continue
   forecast=indices(model_file(m,e,l),m,terrain=terrain)
   all_results['cases'].append(dict(event=e,model=m,lead_h=l,summary=forecast,baseline_tag=tag,judge=judge(e,forecast,main,baseline)))
   print('METRIC',e,m,l,all_results['cases'][-1]['judge'],flush=True)
 if e=='E1':all_results['supplementary_00utc']=indices(truth_file(e,'reference00'),'truth')
with open(f'{ROOT}/metrics_v2.json','x') as f:json.dump(all_results,f,indent=2,allow_nan=False)
print('METRICS_COMPLETE',len(all_results['cases']),flush=True)
fig,ax=plt.subplots(2,3,figsize=(13,8),constrained_layout=True)
for ii,e in enumerate(('E1','E2')):
 for jj,k in enumerate(KEY[e]):
  a=ax[ii,jj];ref=all_results['reference'][e][k]['max']
  for m in ('Pangu6','FuXi'):
   cs=[c for c in all_results['cases'] if c['event']==e and c['model']==m and 'judge' in c];a.plot([c['lead_h'] for c in cs],[c['judge']['absolute_error'][k] for c in cs],marker='o',label=m)
  bs=[all_results['baseline'][f'{e}_P{int(math.ceil(l/24)*24)}'][k]['max'] for l in (12,24,48,72,120)]
  a.plot((12,24,48,72,120),[abs(b-ref) for b in bs],'k--',label='P persistence');a.set(title=f'{e} {k}',xlabel='lead h',ylabel='absolute max error');a.legend(fontsize=7)
fig.savefig(f'{ROOT}/errors_v2.png',dpi=150)
