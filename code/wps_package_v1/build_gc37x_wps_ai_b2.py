#!/usr/bin/env python3
"""Construct paired regional WPS format-5 drivers from native GFS and L37 output.
CRC CPU conversion from numerically verified native GFS files; never download. No PSFC supplied.
"""
import argparse, datetime as dt, hashlib, json, pathlib, sys, os, shutil
import numpy as np, pygrib
from scipy.spatial import cKDTree
from wps_format5 import write_field, readback
EVENT=os.environ['GC37_EVENT']
assert EVENT in ('N8','N9','N10')
PARENT=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
R=pathlib.Path(os.environ['GC37_OPS_ROOT']).resolve()
assert R.parent == PARENT/f'drivers_{EVENT}_v1', R
INPUT_RAW=None
RAW=pathlib.Path(os.environ['GC37_AI_RAW_DIR'])
assert RAW.is_absolute() and RAW.parent == PARENT and RAW.name == f'infer_b2_{EVENT}_{os.environ["GC37_LEAD"]}h_v1', RAW
EVENT_CONFIG=json.loads((R/'event_times_bbox_gc37x.json').read_text())['events'][EVENT]
BOUNDING=EVENT_CONFIG['domain']
EVENT_TIMES=EVENT_CONFIG
LEVELS=[1000,975,950,925,900,850,800,750,700,650,600,550,500,450,400,350,300,250,200,150,100,70,50,30,20,10,7,5,3,2,1]
# actual common table is imported and checked at runtime; do not assume above list is correct
OUTLAT=float(BOUNDING['crop_lat'][0]);OUTLON=float(360+BOUNDING['crop_lon_west_neg'][0]);STEP=.25
SLICES=(slice(int(round((90-BOUNDING['crop_lat'][1])*4)),int(round((90-OUTLAT)*4))+1),slice(int(round(OUTLON*4)),int(round((360+BOUNDING['crop_lon_west_neg'][1])*4))+1))
FIVE={'gh':('GHT','m'),'t':('TT','K'),'u':('UU','m s-1'),'v':('VV','m s-1'),'q':('SPECHUMD','kg kg-1')}
MODEL={'gh':'geopotential','t':'temperature','u':'u_component_of_wind','v':'v_component_of_wind','q':'specific_humidity'}
def get(g,short,level=None,typ=None):
 kw={'shortName':short}
 if level is not None: kw.update(level=level,typeOfLevel=typ or 'isobaricInhPa')
 matches=g.select(**kw)
 if len(matches)!=1: raise ValueError(('field',short,level,typ,len(matches)))
 a=matches[0].values
 if np.ma.isMaskedArray(a): a=a.filled(np.nan)
 return np.asarray(a,dtype='float32')[SLICES][::-1].copy()
def download(t,lead):
 # All boundary files have passed the 93-file numerical gate on CRC.
 name=f'gfs.0p25.{t:%Y%m%d%H}.f{lead:03d}.grib2'
 p=INPUT_RAW/name
 if not p.is_file() or p.stat().st_size<10_000_000:
  raise FileNotFoundError(('verified_input_absent',str(p)))
 return p
def nearest_land_fill(a,land,field,cycle,ledger):
 bad=(~np.isfinite(a))&land
 if not bad.any():return a
 good=np.isfinite(a)&land
 if not good.any():raise ValueError(('no_land_donor',field))
 yy,xx=np.where(good); by,bx=np.where(bad)
 lat=OUTLAT+yy*STEP;lon=OUTLON+xx*STEP
 phi=np.deg2rad(lat);lam=np.deg2rad(lon)
 xyz=np.column_stack((np.cos(phi)*np.cos(lam),np.cos(phi)*np.sin(lam),np.sin(phi)))
 blat=OUTLAT+by*STEP;blon=OUTLON+bx*STEP
 bphi=np.deg2rad(blat);blam=np.deg2rad(blon)
 bxyz=np.column_stack((np.cos(bphi)*np.cos(blam),np.cos(bphi)*np.sin(blam),np.sin(bphi)))
 dist,ind=cKDTree(xyz).query(bxyz)
 for y,x,dy,dx,di in zip(by,bx,yy[ind],xx[ind],dist):
  val=float(a[dy,dx]);a[y,x]=val
  ledger.append({'cycle':cycle,'field':field,'target_index_yx':[int(y),int(x)],'target_lat_lon_east':[float(OUTLAT+y*STEP),float(OUTLON+x*STEP)],'donor_index_yx':[int(dy),int(dx)],'donor_lat_lon_east':[float(OUTLAT+dy*STEP),float(OUTLON+dx*STEP)],'donor_distance_km':float(6371.229*2*np.arcsin(min(1.,di/2))),'filled_value':val})
 return a
def surface(g,cycle,ledger):
 # Soil layers use GRIB depthBelowLandLayer or depthBelowLand; actual inventory is recorded.
 d={}
 simple={'2t':('TT',200100,'K'),'10u':('UU',200100,'m s-1'),'10v':('VV',200100,'m s-1'),
         'prmsl':('PMSL',201300,'Pa'),
         'orog':('SOILHGT',200100,'m'),'lsm':('LANDSEA',200100,'fraction'),
         't_surface':('SKINTEMP',200100,'K'),'sdwe':('SNOW',200100,'kg m-2')}
 for short,(field,lev,units) in simple.items():
  if short=='t_surface':a=get(g,'t',0,'surface')
  elif short=='sdwe':
   try:a=get(g,short)
   except ValueError:a=get(g,'weasd')
  else:a=get(g,short)
  if short=='lsm': a=np.where(a>=.5,1.,0.).astype('float32')
  if short=='sdwe':
   land=d[('LANDSEA',200100)][0]>.5
   bad=~np.isfinite(a)
   a=nearest_land_fill(a,land,field,cycle,ledger)
   a[bad & ~land]=0  # v2.1 ocean-side zero; land gaps use approved donor rule
  d[(field,lev)]=(a,units,short)
 for short,stem,unit in [('st','ST','K'),('soilw','SM','fraction')]:
  allm=g.select(shortName=short)
  for suffix,lo,hi in [('000010',0,10),('010040',10,40),('040100',40,100),('100200',100,200)]:
   candidates=[m for m in allm if str(m.typeOfLevel)=='depthBelowLandLayer' and int(m.scaledValueOfFirstFixedSurface)==lo and int(m.scaledValueOfSecondFixedSurface)==hi and int(m.scaleFactorOfFirstFixedSurface)==2 and int(m.scaleFactorOfSecondFixedSurface)==2]
   if len(candidates)!=1:raise ValueError(('soil',short,suffix,[(str(m.typeOfLevel),m.topLevel,m.bottomLevel) for m in allm]))
   a=candidates[0].values
   if np.ma.isMaskedArray(a):a=a.filled(np.nan)
   a=np.asarray(a,dtype='float32')[SLICES][::-1].copy()
   # Soil over ocean may be masked: use zero explicitly only on non-land support.
   land=d[('LANDSEA',200100)][0]>.5
   bad=~np.isfinite(a)
   a=nearest_land_fill(a,land,stem+suffix,cycle,ledger)
   a[bad & ~land]=0
   d[(stem+suffix,200100)]=(a,unit,f'{short}:{lo}-{hi}')
 return d
def gfs_aloft(g,lev):
 fields={}
 for short in FIVE:
  if short=='q':
   # GFS main file has RH, not native q; calculate saturation vapor pressure
   t=get(g,'t',lev);rh=get(g,'r',lev)
   es=611.2*np.exp(17.67*(t-273.15)/(t-29.65))
   e=np.clip(rh/100*es,0,lev*100*.99)
   val=.622*e/(lev*100-.378*e)
  else:val=get(g,short,lev)
  if short=='gh':val=val # GRIB gh is geopotential height (gpm ~ m)
  fields[short]=val
 return fields
def q2(aloft,soil):
 terrain=soil[('SOILHGT',200100)][0];q=np.full(terrain.shape,np.nan,dtype='float32');used=np.zeros(terrain.shape,bool)
 for lev in LEVELS:
  height=aloft[lev]['gh'];v=aloft[lev]['q']
  yes=(~used)&np.isfinite(height)&(height>terrain)&np.isfinite(v)
  q[yes]=v[yes];used|=yes
 if not np.all(used):raise ValueError(('q2_no_layer',int((~used).sum())))
 return q

def write_one(cycle,lead,arm,aloft,soil,surface_dynamic,root):
 t=cycle+dt.timedelta(hours=lead);stamp=t.strftime('%Y-%m-%d_%H:%M:%S');name=f'FILE:{t:%Y-%m-%d_%H}'
 dest=root/arm/f'{cycle:%Y%m%d%H}'/name;dest.parent.mkdir(parents=True,exist_ok=True)
 if dest.exists():raise FileExistsError(dest)
 qproxy=q2(aloft,soil)
 with dest.open('xb') as f:
  for lev in LEVELS:
   for short,(field,units) in FIVE.items():
    a=aloft[lev][short]
    if not np.isfinite(a).all():raise ValueError(('nonfinite_aloft',arm,lead,short,lev))
    write_field(f,stamp,lead,'NCAR-GFS/GC37',field,units,field,lev*100,OUTLAT,OUTLON,STEP,STEP,a)
  for (field,pressure),(array,units,source) in {**soil,**surface_dynamic,('SPECHUMD',200100):(qproxy,'kg kg-1','v2.2 nearest above soil')}.items():
   if not np.isfinite(array).all():raise ValueError(('nonfinite_surface',field,lead,int(np.count_nonzero(~np.isfinite(array)))))
   write_field(f,stamp,lead,'NCAR-GFS/GC37',field,units,source,pressure,OUTLAT,OUTLON,STEP,STEP,array)
 rb=readback(dest); expected=len(LEVELS)*5+len(soil)+len(surface_dynamic)+1
 if rb['records']!=expected:raise ValueError(('readback_count',rb['records'],expected))
 actual={k:sorted(v['level_pa'] for v in rb['fields'] if v['field']==k and v['level_pa']<200000) for k in ('GHT','TT','UU','VV','SPECHUMD')}
 for k,levs in actual.items():
  if levs!=sorted(x*100 for x in LEVELS):raise ValueError(('level_mismatch',k,levs))
 return {'arm':arm,'cycle':cycle.strftime('%Y%m%d%H'),'lead':lead,'file':str(dest.relative_to(root)),'sha256':rb['sha256'],'records':rb['records'],'q2_min':float(qproxy.min()),'q2_max':float(qproxy.max())}
def cache_surface(cycle, base):
 arrays={f'{field}__{pressure}':array for (field,pressure),(array,units,source) in base.items()}
 path=R/f'SHARED_SURFACE_{cycle}.npz'
 with path.open('xb') as fh:np.savez_compressed(fh,**arrays)
 with (R/f'SHARED_SURFACE_{cycle}.json').open('x') as fh:
  json.dump({f'{field}__{pressure}':{'field':field,'pressure':pressure,'units':units,'source':source} for (field,pressure),(array,units,source) in base.items()},fh,indent=2)
def load_surface(cycle):
 source_root=PARENT/f'drivers_{EVENT}_v1'/f'ops_{EVENT}_{os.environ["GC37_LEAD"]}h_GFS_b2'
 meta=json.loads((source_root/f'SHARED_SURFACE_{cycle}.json').read_text())
 with np.load(source_root/f'SHARED_SURFACE_{cycle}.npz') as z:
  return {(v['field'],v['pressure']):(z[k].copy(),v['units'],v['source']) for k,v in meta.items()}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cycle',required=True);ap.add_argument('--arm',choices=('AI',),required=True);ap.add_argument('--raw-dir',required=True);a=ap.parse_args()
 global INPUT_RAW
 INPUT_RAW=pathlib.Path(a.raw_dir).resolve()
 assert INPUT_RAW == (PARENT/'inputs_N8N9N10_v1'/'raw'/a.cycle).resolve() and INPUT_RAW.is_dir()
 cycle=dt.datetime.strptime(a.cycle,'%Y%m%d%H');steps=int((dt.datetime.fromisoformat(EVENT_TIMES['end'])-cycle).total_seconds()/21600)
 common=[int(x.strip()) for x in (R/'COMMON_LEVELS.txt').read_text().split(',')]
 if common!=LEVELS:raise ValueError(('common_levels_disagree',common,LEVELS))
 root=R.parent
 if a.arm=='GFS':
  native0=pygrib.open(str(download(cycle,0)));ledger=[];soil=surface(native0,a.cycle,ledger)
  with (R/f'SOIL_FILL_SNOWFIX_{a.cycle}.json').open('x') as h: json.dump(ledger,h,indent=2)
  base={k:v for k,v in soil.items() if k[0] not in ('TT','UU','VV','PMSL')}
  cache_surface(a.cycle,base)
 else:
  base=load_surface(a.cycle)
 summaries=[]
 for step in range(steps+1):
  lead=step*6
  if a.arm=='GFS':
   g=pygrib.open(str(download(cycle,lead))) if step else native0
   gfields={lev:gfs_aloft(g,lev) for lev in LEVELS}
   gsurf={k:v for k,v in soil.items() if k[0] in ('TT','UU','VV')} if step==0 else {k:(get(g,short),'K' if short=='2t' else 'm s-1','GFS forecast '+short) for k,short in [(('TT',200100),'2t'),(('UU',200100),'10u'),(('VV',200100),'10v')]}
   gsurf[('PMSL',201300)]=(get(g,'prmsl'),'Pa','GFS forecast MSLP')
   summaries.append(write_one(cycle,lead,'GFS',gfields,base,gsurf,root))
   if step:g.close()
   print('WPS_GFS_DONE',a.cycle,step,flush=True)
   continue
  if step==0:
   source=root/'GFS'/a.cycle/f'FILE:{cycle:%Y-%m-%d_%H}'
   dest=root/'AI'/a.cycle/source.name
   dest.parent.mkdir(parents=True,exist_ok=True)
   with source.open('rb') as src, dest.open('xb') as dst: shutil.copyfileobj(src,dst)
   rb=readback(dest)
   summaries.append({'arm':'AI','cycle':a.cycle,'lead':0,'file':str(dest.relative_to(root)),'sha256':rb['sha256'],'records':rb['records'],'t0_copy_of':str(source.relative_to(root))})
   continue
  else:
   f=RAW/a.cycle/f'step_{step:02d}.npz'
   with np.load(f) as z:
    ai={lev:{short:(z['reg_'+MODEL[short]][i].astype('float32')/(9.80665 if short=='gh' else 1)) for short in FIVE} for i,lev in enumerate([int(v) for v in z['reg_level']]) if int(lev) in LEVELS}
    if sorted(ai)!=sorted(LEVELS):raise ValueError(('AI_LEVELS',sorted(ai)))
    assert np.allclose(z['reg_lat'],np.arange(OUTLAT,BOUNDING['crop_lat'][1]+.0001,.25)) and np.allclose(z['reg_lon'],np.arange(OUTLON,360+BOUNDING['crop_lon_west_neg'][1]+.0001,.25))
   # Use own predicted near-surface fields and MSLP.
   with np.load(f) as z:
    asurf={('TT',200100):(z['reg_2m_temperature'].astype('float32'),'K','GraphCast forecast 2t'),('UU',200100):(z['reg_10m_u_component_of_wind'].astype('float32'),'m s-1','GraphCast forecast 10u'),('VV',200100):(z['reg_10m_v_component_of_wind'].astype('float32'),'m s-1','GraphCast forecast 10v')}
    # The corresponding near-surface fields differ intentionally; terrain, land, soil, snow and skin remain frozen.
   with np.load(f) as z:
    asurf[('PMSL',201300)]=(z['reg_mean_sea_level_pressure'].astype('float32'),'Pa','GraphCast forecast MSLP')
  summaries.append(write_one(cycle,lead,'AI',ai,base,asurf,root))
  print('WPS_AI_DONE',a.cycle,step,flush=True)
 if a.arm=='GFS':native0.close()
 with (R/f'WPS_{a.cycle}_{a.arm}_REPORT.json').open('x') as h: json.dump(summaries,h,indent=2)
if __name__=='__main__':main()
