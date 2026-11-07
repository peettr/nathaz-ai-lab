import os,time,json,hashlib,subprocess,traceback,resource,math
from pathlib import Path
P=Path('/content/l2613'); P.mkdir(exist_ok=True)
def log(*x): print(time.strftime('%H:%M:%S'),*x,flush=True)
def save(d): (P/'metrics.json').write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str))
M={'version':'61ff5547e6fa9079dcd23c1cb4d37ec793194277','start':time.time(),'sources':{}}
try:
 log('install pinned VoxCity in isolated Colab')
 subprocess.run(['pip','install','-q','git+https://github.com/kunifujiwara/VoxCity.git@'+M['version'],'trimesh','rtree','openpyxl','xlrd'],check=True,timeout=3000)
 M['install_seconds']=time.time()-M['start'];save(M)
 import numpy as np, geopandas as gpd, pandas as pd, trimesh,requests
 from pyproj import Transformer
 from shapely.geometry import Polygon
 from voxcity.generator import get_voxcity
 from voxcity.downloader.osm import load_gdf_from_openstreetmap
 from voxcity.downloader.overture import load_gdf_from_overture
 from scipy.ndimage import label,distance_transform_edt,maximum_filter
 log('dependencies ready')
 lat,lon=37.92943,139.05260
 tr=Transformer.from_crs('EPSG:4326','EPSG:32654',always_xy=True)
 inv=Transformer.from_crs('EPSG:32654','EPSG:4326',always_xy=True)
 cx,cy=tr.transform(lon,lat)
 # north-aligned enclosing square of rotated 500m AOI; trim to 500x500 afterward
 h=255
 rect=[inv.transform(cx+dx,cy+dy) for dx,dy in [(-h,-h),(-h,h),(h,h),(h,-h)]]
 M['geographic_rectangle']=rect;save(M)
 for src,fetch in [('OpenStreetMap',load_gdf_from_openstreetmap),('Overture',load_gdf_from_overture)]:
  t=time.time();log('fetch',src)
  try:
   g=fetch(rect)
   g.to_file(P/(src+'.gpkg'),driver='GPKG')
   raw=g
   if src=='OpenStreetMap':
    direct=(raw['height_source']=='explicit').sum() if 'height_source' in raw else 0
    levels=(raw['height_source']=='levels').sum() if 'height_source' in raw else 0
   else:
    # Overture downloader overwrites inferred height; source raw re-query for direct tags
    from overturemaps import core
    bbox=(min(x for x,y in rect),min(y for x,y in rect),max(x for x,y in rect),max(y for x,y in rect))
    orig=[core.geodataframe(k,bbox=bbox) for k in ('building','building_part')]
    direct=sum(int(pd.to_numeric(z.get('height',pd.Series(index=z.index,dtype=float)),errors='coerce').gt(0).sum()) for z in orig)
    levels=sum(int(pd.to_numeric(z.get('num_floors',pd.Series(index=z.index,dtype=float)),errors='coerce').gt(0).sum()) for z in orig)
   M['sources'][src]={'rows':len(g),'direct_height':int(direct),'floors':int(levels),'missing_fraction':1-direct/len(g) if len(g) else None,'fetch_seconds':time.time()-t}
   log(src,M['sources'][src]);save(M)
  except Exception as e:
   M['sources'][src]={'error':repr(e),'traceback':traceback.format_exc()};save(M);log('source failed',src,e);continue
  for resolution in (1.0,0.5):
   key=f'{src}_{resolution:g}m'; t=time.time()
   try:
    # Both land-cover and terrain explicitly non-GEE; no canopy measurement in this trial.
    city=get_voxcity(rect,resolution,building_source=src,building_gdf=g,building_complementary_source='None',land_cover_source='OpenStreetMap',canopy_height_source='Static',dem_source='None',static_tree_height=0,flat_dem=True,gridvis=False,mapvis=False,save_voxcity_data=False,parallel_download=False,output_dir=str(P/key))
    v=city.voxels.classes; bh=city.buildings.heights; ids=city.buildings.ids
    d={'seconds':time.time()-t,'peak_rss_kb':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'voxel_shape':v.shape,'building_shape':bh.shape,'building_cells':int(np.count_nonzero(bh>0)),'top_max':float(np.nanmax(bh)),'voxel_code_buildings':int(np.count_nonzero(v==-3))}
    # record compact plan for independent analysis, no public plots
    np.savez_compressed(P/(key+'.npz'),heights=bh.astype('float32'),ids=ids.astype('int32'),slice2=(v[:,:,int(2/resolution)]==-3).astype('uint8'))
    d['npz_bytes']=(P/(key+'.npz')).stat().st_size
    M[key]=d;save(M);log('done',key,d)
   except Exception as e:
    M[key]={'error':repr(e),'traceback':traceback.format_exc(),'seconds':time.time()-t};save(M);log('failed',key,e)
 # official files download and metadata (independent of VoxCity success)
 api=requests.get('https://zenodo.org/api/records/15429018',timeout=60).json()
 M['zenodo_license']=api.get('metadata',{}).get('license');
 for f in api.get('files',[]):
  if f.get('key') in ('BD_caseE.stl','RS_caseE.csv','readme_caseE.md'):
   url=f.get('links',{}).get('self') or f.get('links',{}).get('content')
   if url:
    r=requests.get(url,timeout=120);r.raise_for_status();(P/f['key']).write_bytes(r.content)
    M.setdefault('official_files',{})[f['key']]={'bytes':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest()}
 save(M)
except Exception as e:
 M['fatal']={'error':repr(e),'traceback':traceback.format_exc()};save(M);log('FATAL',e)
finally:
 M['end']=time.time();M['elapsed_seconds']=M['end']-M['start'];save(M)
 (P/'run.done').write_text(str(time.time()))
 log('DONE',M['elapsed_seconds'])
