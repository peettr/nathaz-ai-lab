"""Colab-only read-only source comparison; NOAA f00 range GRIB samples."""
import pathlib,urllib.request,io,json,time
import numpy as np
from scipy.ndimage import uniform_filter
from eccodes import codes_grib_new_from_file,codes_get,codes_get_array,codes_release
import h5py
P=pathlib.Path('/content/l264ctrl05'); OUT=P/'texas';OUT.mkdir(exist_ok=True)
ROOT=P/'AERO_ODE'
BASE='https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.20240401/conus/hrrr.t00z.wrfsfcf00.grib2'
idx=urllib.request.urlopen(BASE+'.idx',timeout=40).read().decode().splitlines()
rows=[line.split(':') for line in idx]
fields={'HGT':'HGT:surface','VGTYP':'VGTYP:surface'}
def get(name,pat):
 i=next(i for i,r in enumerate(rows) if ':'.join(r[3:5])==pat)
 start=int(rows[i][1]);end=int(rows[i+1][1])-1
 req=urllib.request.Request(BASE,headers={'Range':f'bytes={start}-{end}'})
 with urllib.request.urlopen(req,timeout=90) as resp:
  assert resp.status==206,(resp.status,name)
  data=resp.read()
 assert len(data)==end-start+1,(name,len(data),end-start+1)
 f=OUT/(name+'.grib2');f.write_bytes(data)
 with f.open('rb') as h: g=codes_grib_new_from_file(h)
 assert g is not None
 nx=int(codes_get(g,'Ni'));ny=int(codes_get(g,'Nj'))
 vals=np.asarray(codes_get_array(g,'values'),dtype=np.float32).reshape(ny,nx)
 if name=='HGT':
  lats=np.asarray(codes_get_array(g,'latitudes'),dtype=np.float32).reshape(ny,nx)
  lons=np.asarray(codes_get_array(g,'longitudes'),dtype=np.float32).reshape(ny,nx)
  np.save(OUT/'noaa_lat.npy',lats);np.save(OUT/'noaa_lon.npy',lons)
 print('NOAA',name,'shape',vals.shape,'minmax',float(vals.min()),float(vals.max()),'gridType',codes_get(g,'gridType'),'metadata',[(k,str(codes_get(g,k))) for k in ('shortName','name','typeOfLevel')],flush=True)
 codes_release(g);return vals
for n,pat in fields.items():
 v=get(n,pat);np.save(OUT/(n+'.npy'),v)
lats=np.load(OUT/'noaa_lat.npy');lons=np.load(OUT/'noaa_lon.npy');geo=np.load(OUT/'HGT.npy');vg=np.load(OUT/'VGTYP.npy');sf=geo
west=ROOT/'AERO_Surface_WD/Hrrr_rb/data'
wlat=np.load(west/'hrrr_west_lat.npy');wlon=np.load(west/'hrrr_west_lon.npy')
print('west coords',wlat.shape,wlon.shape,[(float(x.min()),float(x.max())) for x in (wlat,wlon)],'noaa corners',[(float(lats[y,x]),float(lons[y,x])) for y,x in ((0,0),(0,-1),(-1,0),(-1,-1))],flush=True)
# Exact grid registration by nearest first corner, test orientation explicitly.
for z in ((0,0),(0,-1),(-1,0),(-1,-1)):
 a,b=float(wlat[z]),float(wlon[z]%360); d=(lats-a)**2+(((lons-b+180)%360)-180)**2
 iy,ix=np.unravel_index(d.argmin(),d.shape)
 print('west_corner',z,'target',a,b,'NOAA index',iy,ix,'angular_error',float(np.sqrt(d[iy,ix])),flush=True)
# West array uses (y,x) by shipped source manager's .T -> (x,y).
a,b=float(wlat[0,0]),float(wlon[0,0]%360);d=(lats-a)**2+(((lons-b+180)%360)-180)**2
y,x=np.unravel_index(d.argmin(),d.shape);h,w=wlat.shape
assert y+h<=geo.shape[0] and x+w<=geo.shape[1]
coorderr=float(np.max(np.abs(lats[y:y+h,x:x+w]-wlat)))+float(np.max(np.abs(((lons[y:y+h,x:x+w]-wlon+180)%360)-180)))
print('west_index',y,x,'coord_max_sum_degree',coorderr,flush=True)
if coorderr>0.01:raise RuntimeError('HRRR west grid registration mismatch')
np.save(OUT/'west_offsets.npy',np.array([y,x]))
# Surface author's geo HDF5 normalization is per region. Compare raw source first.
with h5py.File(west/'west_geo_interpolate.h5') as f:
 author=f['fields'][:];print('AUTHOR_GEO shape',author.shape,'range',float(author.min()),float(author.max()),flush=True)
def cmp(name,pred,ref):
 a=np.asarray(pred,dtype=np.float64).reshape(-1);b=np.asarray(ref,dtype=np.float64).reshape(-1)
 assert a.shape==b.shape,(name,a.shape,b.shape)
 ok=np.isfinite(a)&np.isfinite(b)
 if not ok.all():print('NONFINITE',name,int((~ok).sum()),flush=True)
 corr=float(np.corrcoef(a[ok],b[ok])[0,1]) if a[ok].std()>0 and b[ok].std()>0 else None
 return {'channel':name,'corr':corr,'max_abs_diff':float(np.max(np.abs(a[ok]-b[ok]))),'source_range':[float(a.min()),float(a.max())],'west_range':[float(b.min()),float(b.max())]}
G=geo[y:y+h,x:x+w];V=vg[y:y+h,x:x+w];S=sf[y:y+h,x:x+w]
# allow one singleton dimension in author geo
r=[];r.append(cmp('geo_raw',G,author.squeeze()))
R=ROOT/'AERO_Surface_WD/Hrrr_rb/data'
# Centered differences at 3-km grid spacing, domain z score for derived terrain.
dy,dx=np.gradient(G.astype(np.float64),3000.,3000.)
def zscore(a):return (a-a.mean())/(a.std()+1e-6)
slope=zscore(np.arctan(np.hypot(dx,dy)))
tpi=zscore(G-uniform_filter(G,size=5,mode='nearest'))
# downhill clockwise from north, x east and y north when scan orientation increases
aspect=np.arctan2(-dx,-dy)
features={'slope':slope,'tpi':tpi,'aspect_sin':zscore(np.sin(aspect)),'aspect_cos':zscore(np.cos(aspect)),'roughness_log_z0_norm':zscore(np.log(np.maximum(S,1e-6))),'urban_mask':(V==13),'forest_mask':np.isin(V,[1,2,3,4,5]),'cropland_mask':np.isin(V,[12,14]),'grassland_mask':np.isin(V,[6,7,8,9,10])}
for key,pred in features.items():
 ref=np.load(R/(key+'.npy'));rr=cmp(key,pred,ref);rr['noaa_grib']={'slope':'HGT:surface','tpi':'HGT:surface','aspect_sin':'HGT:surface','aspect_cos':'HGT:surface','roughness_log_z0_norm':'SFCR:surface'}.get(key,'VGTYP:surface');r.append(rr);print('COMPARE',rr,flush=True)
(OUT/'west_comparison.json').write_text(json.dumps({'source':'NOAA HRRR 2024-04-01 00Z f00; AERO-ODE commit 99516ae9cf','grid_offset':[int(y),int(x)],'coord_error_deg':coorderr,'channels':r},indent=2))
(OUT/'static_probe.done').write_text('ok\n')
