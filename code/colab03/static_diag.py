"""Colab-only NOAA f00 static-field provenance and west compatibility check."""
import io,urllib.request,pathlib,json,numpy as np,h5py,sys
from scipy.spatial import cKDTree
import eccodes
P=pathlib.Path('/content/l264texas01'); R=P/'AERO_ODE'
URL='https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.20240401/conus/hrrr.t00z.wrfsfcf00.grib2'
idx=urllib.request.urlopen(URL+'.idx',timeout=30).read().decode().splitlines()
entries=[]
for row in idx:
 parts=row.split(':');entries.append((int(parts[1]),':'.join(parts[3:]),row))
def field(token):
 hits=[i for i,(offset,label,_) in enumerate(entries) if token in label]
 if len(hits)!=1:raise RuntimeError(f'nonunique {token}: {[(entries[i][2]) for i in hits]}')
 i=hits[0]; start=entries[i][0];end=entries[i+1][0]-1 if i+1<len(entries) else None
 if end is None:raise RuntimeError('unknown end')
 req=urllib.request.Request(URL,headers={'Range':f'bytes={start}-{end}'})
 with urllib.request.urlopen(req,timeout=90) as response:
  if response.status!=206:raise RuntimeError('HTTP range ignored')
  raw=response.read()
 g=eccodes.codes_new_from_message(raw)
 try:
  nx=eccodes.codes_get(g,'Nx');ny=eccodes.codes_get(g,'Ny')
  vals=eccodes.codes_get_values(g).reshape(ny,nx)
  lat=np.asarray(eccodes.codes_get_array(g,'latitudes')).reshape(ny,nx)
  lon=np.asarray(eccodes.codes_get_array(g,'longitudes')).reshape(ny,nx)
  print('FIELD',token,'record',entries[i][2],'shape',vals.shape,'latcorners',lat[0,0],lat[-1,-1],'loncorners',lon[0,0],lon[-1,-1],'minmax',float(vals.min()),float(vals.max()),flush=True)
  return vals,lat,lon
 finally:eccodes.codes_release(g)
try:
 hgt,lat,lon=field('HGT:surface:anl:')
 west=R/'AERO_Surface_WD/Hrrr_rb/data'
 wlat=np.load(west/'hrrr_west_lat.npy');wlon=np.load(west/'hrrr_west_lon.npy')
 print('WEST',wlat.shape,wlon.shape,wlat.min(),wlat.max(),wlon.min(),wlon.max(),flush=True)
 # KD-tree maps geographic coordinates across HRRR native grid; no interpolation in a same-grid cut.
 xyz=np.column_stack([lat.ravel(),((lon.ravel()+180)%360)-180]); q=np.column_stack([wlat.ravel(),((wlon.ravel()+180)%360)-180]);dist,indices=cKDTree(xyz).query(q,workers=4)
 print('WEST_NEAREST_DEG',np.percentile(dist,[0,50,95,100]),flush=True)
 print('WEST_INDEX_CORNERS',[(int(indices.reshape(wlat.shape)[i,j]//hgt.shape[1]),int(indices.reshape(wlat.shape)[i,j]%hgt.shape[1])) for i,j in ((0,0),(0,-1),(-1,0),(-1,-1))],flush=True)
 with h5py.File(west/'west_geo_interpolate.h5') as f:
  geo=f['fields'][:]
  print('WEST_GEO',geo.shape,dict(f['fields'].attrs),float(geo.min()),float(geo.max()),flush=True)
  source=np.squeeze(geo).T
  for mode,base in [('m',hgt),('geopot',hgt*9.80665)]:
   mapped=base.ravel()[indices].reshape(wlat.shape)
   if source.shape!=mapped.shape:print('SHAPE_MISMATCH',source.shape,mapped.shape,flush=True);continue
   a=source.ravel();b=mapped.ravel()
   corr=float(np.corrcoef(a,b)[0,1]);maxd=float(np.max(np.abs(a-b)))
   corrz=float(np.corrcoef((a-a.mean())/(a.std()+1e-6),(b-b.mean())/(b.std()+1e-6))[0,1])
   print('COMPARE',mode,'corr',corr,'maxabs',maxd,'corrz',corrz,flush=True)
 vgt,_,_=field('VGTYP:surface:anl:');rough,_,_=field('SFCR:surface:anl:')
 print('VGTYP_CLASSES',np.unique(vgt,return_counts=True)[0].tolist(),flush=True)
 print('SFCR',float(np.min(rough)),float(np.max(rough)),flush=True)
 (P/'static_diag.done').write_text('ok')
except BaseException:
 import traceback;traceback.print_exc();(P/'static_diag.failed').write_text(traceback.format_exc());raise
