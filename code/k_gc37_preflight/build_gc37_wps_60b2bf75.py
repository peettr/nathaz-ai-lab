#!/usr/bin/env python3
"""Construct paired regional WPS format-5 drivers from native GFS and L37 output.
Run only on Colab. No replacement of existing output. No PSFC supplied.
"""
import argparse, datetime as dt, hashlib, json, pathlib, sys, time, urllib.request
import numpy as np, pygrib
from scipy.spatial import cKDTree
sys.path.insert(0, '/content/r234c_gc37_scripts')
from wps_format5 import write_field, readback
R=pathlib.Path('/content/r234c_gc37_60b2bf75')
LEVELS=[1000,975,950,925,900,850,800,750,700,650,600,550,500,450,400,350,300,250,200,150,100,70,50,30,20,10,7,5,3,2,1]
# actual common table is imported and checked at runtime; do not assume above list is correct
SLICES=(slice(152,241),slice(976,1081)) # GRIB north-to-south, longitude 244..270 inclusive
OUTLAT=30.; OUTLON=244.; STEP=.25
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
 name=f'gfs.0p25.{t:%Y%m%d%H}.f{lead:03d}.grib2';p=R/'raw'/name
 if not p.exists():
  u=f'https://osdf-director.osg-htc.org/ncar/gdex/d084001/2020/{t:%Y%m%d}/{name}'
  p.parent.mkdir(parents=True,exist_ok=True)
  q=p.with_suffix('.partial')
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=180) as resp,q.open('xb') as h:
   while chunk:=resp.read(4*1024*1024):h.write(chunk)
  q.rename(p);print('GFS_DOWNLOAD',u,p.stat().st_size,flush=True)
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
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cycle',required=True);a=ap.parse_args()
 cycle=dt.datetime.strptime(a.cycle,'%Y%m%d%H');steps=int((dt.datetime(2020,6,9,12)-cycle).total_seconds()/21600)
 common=[int(x.strip()) for x in (R/'COMMON_LEVELS.txt').read_text().split(',')]
 if common!=LEVELS:raise ValueError(('common_levels_disagree',common,LEVELS))
 root=R/'drivers_gc37_v1_snowfix';root.mkdir(exist_ok=True)
 native0=pygrib.open(str(download(cycle,0)));ledger=[];soil=surface(native0,a.cycle,ledger)
 (R/f'SOIL_FILL_SNOWFIX_{a.cycle}.json').write_text(json.dumps(ledger,indent=2))
 # Both groups use same t0 surface/soil fields at every forecast lead, except AI forecast near surface.
 base={k:v for k,v in soil.items() if k[0] not in ('TT','UU','VV','PMSL')}
 # Same-cycle GFS f000 land/soil/2m/10m fields frozen across all leads.
 summaries=[]
 for step in range(steps+1):
  lead=step*6;g=pygrib.open(str(download(cycle,lead))) if step else native0
  gfields={lev:gfs_aloft(g,lev) for lev in LEVELS}
  gsurf={k:v for k,v in soil.items() if k[0] in ('TT','UU','VV')}
  gsurf[('PMSL',201300)]=(get(g,'prmsl'),'Pa','GFS forecast MSLP')
  summaries.append(write_one(cycle,lead,'GFS',gfields,base,gsurf,root))
  if step==0:
   ai=gfields;asurf=gsurf
  else:
   f=R/f'forecast_{a.cycle}_full_{steps}step'/f'step_{step:02d}.npz'
   with np.load(f) as z:
    ai={lev:{short:(z['reg_'+MODEL[short]][i].astype('float32')/(9.80665 if short=='gh' else 1)) for short in FIVE} for i,lev in enumerate([int(v) for v in z['reg_level']]) if int(lev) in LEVELS}
    if sorted(ai)!=sorted(LEVELS):raise ValueError(('AI_LEVELS',sorted(ai)))
    assert np.allclose(z['reg_lat'],np.arange(30,52.0001,.25)) and np.allclose(z['reg_lon'],np.arange(244,270.0001,.25))
   # Same-cycle GFS f000 near-surface fields, but model-predicted MSLP.
   asurf={k:v for k,v in gsurf.items() if k[0]!='PMSL'}
   with np.load(f) as z:
    asurf[('PMSL',201300)]=(z['reg_mean_sea_level_pressure'].astype('float32'),'Pa','GraphCast forecast MSLP')
  summaries.append(write_one(cycle,lead,'AI',ai,base,asurf,root))
  if step:g.close()
  print('WPS_PAIR_DONE',a.cycle,step,flush=True)
 native0.close()
 (R/f'WPS_{a.cycle}_REPORT.json').write_text(json.dumps(summaries,indent=2))
if __name__=='__main__':main()
