#!/usr/bin/env python3
"""Post-process completed immutable H08 batches, annual block bootstrap, and figures."""
import csv, json, math, pathlib, zipfile, requests, time
from collections import defaultdict
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams
ROOT=pathlib.Path('/content/b2');OUT=ROOT/'products';OUT.mkdir(exist_ok=True)
SITES=list(csv.DictReader((ROOT/'sites.csv').open())); N=len(SITES); assert N==19

def read_catalog(name):
 files=sorted((ROOT/'results').glob(name+'_*.npz'));assert len(files)>=2
 arr=[np.load(f) for f in files];ids=np.concatenate([x['ids'] for x in arr]);years=np.concatenate([x['years'] for x in arr]);peaks=np.concatenate([x['peaks'] for x in arr]);ratios=np.concatenate([x['ratios'] for x in arr]);
 assert len(ids)==len(np.unique(ids)) and peaks.shape==(len(ids),3,N)
 if name=='raft':years=np.floor(ids/14.5).astype(int); nyrs=40000/14.5;assert ids.max()<40000
 else:nyrs=10000;assert years.min()>=0 and years.max()<10000
 return ids,years,peaks,ratios,nyrs

def return_value(v,T,nyrs,nall,weights=None):
 pos=np.where(v>0)[0];order=pos[np.argsort(v[pos])[::-1]]
 if not len(order):return None
 target=(nall+1)*nyrs/(T*nall)
 if weights is None:
  ranks=np.arange(1,len(order)+1,dtype='float64')
  if len(ranks)<2 or target<1 or target>ranks[-1]:return None
  return float(np.interp(target,ranks,v[order]))
 ww=weights[order];good=ww>0;order=order[good];ww=ww[good]
 if len(order)<2:return None
 end=np.cumsum(ww).astype('float64');start=end-ww+1
 if target<1 or target>end[-1]:return None
 # Duplicate bootstrap years repeat the same storm peak for each event copy.
 ranks=np.column_stack((start,end)).ravel();vals=np.repeat(v[order],2)
 return float(np.interp(target,ranks,vals))

def boot(v,years,nyrs,nall,T,nboot=300):
 rg=np.random.default_rng(20261014);ny=int(math.ceil(nyrs));all_years=np.arange(ny);ans=np.empty(nboot);ans[:]=np.nan
 valid=(years>=0)&(years<ny);assert valid.all()
 for z in range(nboot):
  counts=np.bincount(rg.integers(0,ny,size=ny),minlength=ny);weights=counts[years]
  # Number of all storms in a resampled year is unobserved for omitted distant
  # STORM events; Nstorm/(Nstorm+1) practically 1, retained frozen nall.
  x=return_value(v,T,nyrs,nall,weights)
  if x is not None:ans[z]=x
 good=ans[np.isfinite(ans)]
 return [float(np.quantile(good,.05)),float(np.quantile(good,.95))] if len(good)>=270 else [None,None]

def contributions(v,r,threshold):
 if threshold is None:return None
 selected=np.where(v>=threshold)[0];r=r[selected];finite=np.isfinite(r);r=r[finite]
 counts=[int(np.sum(r<1)),int(np.sum((r>=1)&(r<=3))),int(np.sum(r>3))]
 return dict(n=int(len(selected)),valid_rmw=int(len(r)),missing_rmw=int(len(selected)-len(r)),bins=counts,shares=[float(x/len(r)) if len(r) else None for x in counts])

def coast_distance():
 import geopandas as gpd
 from shapely.geometry import Point,box
 from shapely.ops import unary_union,transform,nearest_points
 from pyproj import Transformer
 p=ROOT/'ne_10m_coastline.zip'
 if not p.exists():
  r=requests.get('https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_coastline.zip',timeout=80);r.raise_for_status();p.write_bytes(r.content)
 g=gpd.read_file('zip://'+str(p));g=g[g.intersects(box(-101,22,-72,39))]
 # Full geometry includes Eurasian coastline; box-filter retains only relevant segments.
 lines=unary_union(g.geometry.values)
 values=[]
 for site in SITES:
  lat=float(site['lat']);lon=float(site['lon']);point=Point(lon,lat)
  n=nearest_points(point,lines)[1]
  proj=Transformer.from_crs('EPSG:4326',f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m',always_xy=True).transform
  values.append(round(transform(proj,point).distance(transform(proj,n))/1000,3))
 return values

def main():
 ra=read_catalog('raft');st=read_catalog('storm');data={'raft':ra,'storm':st};coast=coast_distance(); rows=[];detail={};checks={}
 for name,(ids,years,peaks,ratios,nyrs) in data.items():
  marker=json.loads((ROOT/'results'/f'{name}_complete.json').read_text()); checks[name]=marker
  assert marker['counts']['failed']==0 and marker['counts']['selected']==len(ids)
  if name=='raft':assert marker['counts']['raw']==40000
  nall=marker['counts']['raw']
  for j,site in enumerate(SITES):
   key=site['site'];detail.setdefault(key,{})[name]={};v=peaks[:,0,j];r=ratios[:,0,j]
   for T in (50,700):
    main=return_value(v,T,nyrs,nall)
    interval=boot(v,years,nyrs,nall,T)
    detail[key][name][f'v{T}']=main;detail[key][name][f'ci{T}']=interval
    detail[key][name][f'contrib{T}']=contributions(v,r,main)
   detail[key][name]['poci_sensitivity']={str(poci):{f'v{T}':return_value(peaks[:,k,j],T,nyrs,nall) for T in (50,700)} for k,poci in [(1,1005),(2,1015)]}
   detail[key][name]['rate_sensitivity']={str(rate):{f'v{T}':return_value(v,T,40000/rate,nall) for T in (50,700)} for rate in (10,20)} if name=='raft' else {}
   detail[key][name]['event_n_gt0']=int(np.sum(v>0))
 for j,site in enumerate(SITES):
  key=site['site'];a=float(site['asce_v700_ms']);b=float(site['asce_v50_ms']) if site['asce_v50_ms'] else None
  row={'site':key,'state':site['state'],'lat':site['lat'],'lon':site['lon'],'coast_km':coast[j],
   'asce50_ms':b,'asce700_ms':a}
  for name in ('raft','storm'):
   d=detail[key][name]
   for T in (50,700):row[f'{name}{T}_ms']=d[f'v{T}'];row[f'{name}{T}_ci90_lo_ms']=d[f'ci{T}'][0];row[f'{name}{T}_ci90_hi_ms']=d[f'ci{T}'][1]
   row[name+'700_bias_pct']=round(100*(d['v700']/a-1),4) if d['v700'] else None
  rows.append(row)
 with (OUT/'return_levels.csv').open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
 (OUT/'details.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2))
 (OUT/'run_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
 valid=[r for r in rows if r['raft700_ms'] is not None and r['storm700_ms'] is not None and r['asce700_ms'] is not None]
 s=np.array([r['storm700_bias_pct']/100 for r in valid]);a=np.array([r['raft700_bias_pct']/100 for r in valid]);
 med_st=float(np.median(s));mad_st=float(np.median(np.abs(s)));mad_ra=float(np.median(np.abs(a)))
 gates={'n':len(valid),'gate0_median_signed_bias':med_st,'gate0_pass':bool(len(valid)>=12 and abs(med_st)<=.2),
  'storm_median_abs_bias':mad_st,'raft_median_abs_bias':mad_ra,
  'gate1_a':bool(mad_ra<=.15),'gate1_b':bool(mad_ra<=1.1*mad_st),'gate1_pass':bool(len(valid)>=12 and abs(med_st)<=.2 and mad_ra<=.15 and mad_ra<=1.1*mad_st)}
 groups={'TX-LA':['KBRO','KCRP','KGLS','KLCH','KMSY'],'MS-Panhandle':['KGPT','KMOB','KPNS','KAAF'],'Peninsula-Keys':['KTPA','KRSW','KEYW','KMIA','KPBI','KMLB'],'GA-NC':['KJAX','KCHS','KILM','KHSE']}
 gates['segments']={name:{'n':len(v),'raft_signed_median':float(np.median([r['raft700_ms']/r['asce700_ms']-1 for r in v])),'storm_signed_median':float(np.median([r['storm700_ms']/r['asce700_ms']-1 for r in v])),'raft_vs_storm_signed_median':float(np.median([r['raft700_ms']/r['storm700_ms']-1 for r in v]))} for name,ids in groups.items() if (v:=[r for r in valid if r['site'] in ids])}
 coast_groups={'<10':[r for r in valid if r['coast_km']<10],'10-50':[r for r in valid if 10<=r['coast_km']<=50],'>50':[r for r in valid if r['coast_km']>50]}
 gates['coast']={name:{'n':len(v),'raft_median_abs_bias':float(np.median([abs(r['raft700_ms']/r['asce700_ms']-1) for r in v])) if v else None,'storm_median_abs_bias':float(np.median([abs(r['storm700_ms']/r['asce700_ms']-1) for r in v])) if v else None} for name,v in coast_groups.items()}
 gates['spatial_relative_abs_median']=float(np.median([abs(r['raft700_ms']/r['storm700_ms']-1) for r in valid]));gates['spatial_relative_pass']=bool(gates['spatial_relative_abs_median']<=.15 and all(abs(x['raft_vs_storm_signed_median'])<=.25 for x in gates['segments'].values()) and len(gates['segments'])==4)
 (OUT/'gates.json').write_text(json.dumps(gates,indent=2))
 x=np.arange(N);fig,ax=plt.subplots(figsize=(16,6));ax.plot(x,[r['asce700_ms'] for r in rows],'k-o',label='ASCE 7-22 (all-hazard)')
 for name,color,shift in [('raft','#c25126',-.12),('storm','#27729c',.12)]:
  y=np.array([r[f'{name}700_ms'] for r in rows]);low=np.array([r[f'{name}700_ci90_lo_ms'] for r in rows]);high=np.array([r[f'{name}700_ci90_hi_ms'] for r in rows]);ax.errorbar(x+shift,y,yerr=np.array([y-low,high-y]),fmt='o-',c=color,capsize=3,linewidth=1.5,label=name.upper()+' (90% year-block bootstrap)')
 ax.set_xticks(x,[r['site'] for r in rows],rotation=50);ax.set_ylabel('V700 (m/s), 10 m, Exposure C, 3-s gust');ax.grid(alpha=.2);ax.legend(loc='upper center',bbox_to_anchor=(.5,1.2),ncol=3);fig.subplots_adjust(bottom=.22,top=.76)
 fig.text(.5,.015,'Data: RAFT Xu et al. (2024) Zenodo 10392725; STORM Bloemendaal et al. (2020) 4TU v4; ASCE 7-22 GIS ImageServer (50/700 MRI). H08 CLIMADA 6.1.0; RAFT annual rate ASSUMED 14.5 storms/y; POCI ASSUMED 1010 hPa.',ha='center',fontsize=8)
 fig.savefig(OUT/'v700_comparison.png',dpi=160);plt.close(fig)
 print('POST_DONE',json.dumps(gates,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
