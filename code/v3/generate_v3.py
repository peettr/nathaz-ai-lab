"""PLATEAU 2022 CityGML -> VoxCity, immutable 2022 tile and orientation gate."""
import time,json,traceback,subprocess,resource,hashlib
from pathlib import Path
P=Path('/content/l2613v3'); D={'start':time.time(),'version':'2022 v2 / product spec 2.3','commit':'61ff5547e6fa9079dcd23c1cb4d37ec793194277'}
def save(): (P/'generation.json').write_text(json.dumps(D,indent=2,ensure_ascii=False,default=str))
def log(*x): print(time.strftime('%H:%M:%S'),*x,flush=True); D['stage']=' '.join(map(str,x));save()
def dig(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return {'bytes':p.stat().st_size,'sha256':h.hexdigest(),'mtime':p.stat().st_mtime}
try:
 cov=json.loads((P/'coverage_adjacent.json').read_text());assert cov['coverage'] and not cov.get('error'),cov
 log('install pinned')
 subprocess.run(['pip','install','-q','git+https://github.com/kunifujiwara/VoxCity.git@'+D['commit'],'trimesh','rtree','xlrd','scikit-image'],check=True,timeout=1000)
 import numpy as np,pandas as pd,geopandas as gpd
 from shapely.geometry import Polygon
 from shapely.ops import transform
 from pyproj import CRS,Transformer
 from rasterio.features import rasterize
 from affine import Affine
 from voxcity.downloader.citygml import load_buid_dem_veg_from_citygml,get_tile_polygon_from_filename
 from voxcity.utils.orientation import AXES
 assert AXES==('north','east','up'),AXES
 lat,lon=37.92943,139.05260; theta=np.deg2rad(-1);c,s=np.cos(theta),np.sin(theta)
 ll=CRS.from_epsg(4326);ae=CRS.from_proj4(f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs')
 forward=Transformer.from_crs(ll,ae,always_xy=True);inverse=Transformer.from_crs(ae,ll,always_xy=True)
 def togeo(x,y):return inverse.transform(c*x-s*y,s*x+c*y)
 def tooff(x,y):
  e,n=forward.transform(x,y);return c*e+s*n,-s*e+c*n
 rect=[togeo(x,y) for x,y in [(-250,-250),(-250,250),(250,250),(250,-250)]]
 D['rectangle']=rect
 for x in cov['target_mesh_files']:
  tile=Polygon(get_tile_polygon_from_filename(Path(x).name));D.setdefault('tile_bounds',{})[x]=tile.bounds
  assert tile.intersects(Polygon(rect)),('tile does not intersect rectangle',tile.bounds,rect)
 # The loader must see udx/bldg; archive may have one top-level parent.
 path=P/cov['target_mesh_files'][0];udx=next(q for q in path.parents if q.name=='udx');root=udx.parent
 log('parse 2022 CityGML',str(path))
 g,_,_=load_buid_dem_veg_from_citygml(citygml_path=str(root),rectangle_vertices=rect)
 assert g is not None and len(g)>0,'CityGML parser returned zero buildings'
 # Confirm latitude-longitude swap: before swap parser has (37.x,139.x), after swap must be (139.x,37.x).
 D['crs_after_parser']=str(g.crs);g=g.to_crs('EPSG:4326');D['sample_bounds']=g.total_bounds.tolist()
 assert 138<g.total_bounds[0]<140 and 37<g.total_bounds[1]<39,('coordinate swap incorrect',D['sample_bounds'])
 # Clip footprints by the exact official-oriented rectangular polygon; preserve source attributes.
 g=g[g.intersects(Polygon(rect))].copy();g['height_direct']=pd.to_numeric(g['height'],errors='coerce')
 D['rows']=len(g);D['direct_height_count']=int(g['height_direct'].notna().sum());D['height_missing_fraction']=1-D['direct_height_count']/max(1,len(g));D['fields']=list(g.columns)
 assert len(g)>0
 g.to_file(P/'PLATEAU.gpkg',driver='GPKG');log('parsed',len(g),'direct heights',D['direct_height_count'])
 upstream=rasterize([(transform(tooff,geom),1) for geom in g.geometry if geom is not None and not geom.is_empty],out_shape=(500,500),transform=Affine(1,0,-250,0,1,-250),dtype='uint8').astype(bool)
 ii,jj=np.indices((500,500));disc=np.hypot(jj+.5-250,ii+.5-250)<190
 D['source_mask_cells_in_disk']=int((upstream&disc).sum());save()
 # Distinct process per resolution to bound and measure peak RSS.
 one=P/'generate_one.py'
 one.write_text('''import json,sys,time,resource,numpy as np,geopandas as gpd\nfrom pathlib import Path\nfrom voxcity.generator import get_voxcity\np=Path(sys.argv[1]);r=float(sys.argv[2]);rect=json.loads(sys.argv[3]);g=gpd.read_file(p/'PLATEAU.gpkg');t=time.monotonic()\nc=get_voxcity(rect,r,building_source='GeoDataFrame',building_gdf=g,building_complementary_source='None',land_cover_source='OpenStreetMap',canopy_height_source='Static',dem_source='None',static_tree_height=0,flat_dem=True,gridvis=False,mapvis=False,save_voxcity_data=False,parallel_download=False,output_dir=str(p/f'PLATEAU_{r:g}'))\na=c.voxels.classes;np.save(p/f'PLATEAU_{r:g}.npy',a);np.save(p/f'PLATEAU_{r:g}_heights.npy',c.buildings.heights);np.save(p/f'PLATEAU_{r:g}_ids.npy',c.buildings.ids);print('RESULT_JSON='+json.dumps({'seconds':time.monotonic()-t,'peak_rss_kb':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'shape':a.shape,'solid_cells':int((a==-3).sum()),'height_grid_max':float(np.nanmax(c.buildings.heights))}),flush=True)''')
 for r in [1,.5]:
  log('generation',r);t=time.monotonic();z=subprocess.run(['python',str(one),str(P),str(r),json.dumps(rect)],capture_output=True,text=True,timeout=1800)
  (P/f'PLATEAU_{r:g}.log').write_text(z.stdout+'\nSTDERR\n'+z.stderr[-12000:])
  if z.returncode:raise RuntimeError(f'{r}m generation rc={z.returncode}: '+z.stderr[-2000:])
  key=f'{r:g}m';D[key]=json.loads(z.stdout.split('RESULT_JSON=')[-1].splitlines()[0]);D[key]['outer_seconds']=time.monotonic()-t
  p=P/f'PLATEAU_{r:g}.npy';D[key]['field']=dig(p);a=np.load(p,mmap_mode='r')
  assert a.shape[:2]==(round(500/r),round(500/r)),('not 500m square',a.shape)
  if r==1:
   solid=np.asarray(a[:,:,2]==-3)
   forms={'id':solid,'flip_i':solid[::-1,:],'flip_j':solid[:,::-1],'flip_both':solid[::-1,::-1],'transpose':solid.T,'transpose_flip_i':solid.T[::-1,:],'transpose_flip_j':solid.T[:,::-1],'transpose_flip_both':solid.T[::-1,::-1]}
   D['gate']={k:float(((v&upstream)&disc).sum()/max(1,((v|upstream)&disc).sum())) for k,v in forms.items()}
   D['gate_pass']=D['gate']['id']>=.7 and D['gate']['id']>max(v for k,v in D['gate'].items() if k!='id')
   log('GATE',D['gate_pass'],D['gate'])
   if not D['gate_pass']:raise RuntimeError('hard gate failed; downstream forbidden')
  save()
 D['end']=time.time();log('generated successfully')
except Exception as e:
 D['error']=repr(e);D['traceback']=traceback.format_exc();log('ERROR',repr(e))
finally:
 D['end']=time.time();save();(P/'generation.done').write_text('done');print('GENERATION_DONE',D.get('error','ok'),flush=True)
