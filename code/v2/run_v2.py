"""L26.13 v2: isolated Colab CPU; fixed pose; gate before downstream metrics."""
import os, time, json, traceback, hashlib, zipfile, struct, resource
from pathlib import Path
P=Path('/content/l2613v2'); P.mkdir(exist_ok=True)
M=json.loads((P/'metrics.json').read_text()) if (P/'metrics.json').exists() else {'commit':'61ff5547e6fa9079dcd23c1cb4d37ec793194277','start':time.time(),'sources':{},'pose':{'lat':37.92943,'lon':139.05260,'theta_deg':-1},'stages':[]}
def save(): (P/'metrics.json').write_text(json.dumps(M,ensure_ascii=False,indent=2,default=str))
def note(*a): print(time.strftime('%H:%M:%S'),*a,flush=True); M['stages'].append([time.time(),*map(str,a)]);save()
def digest(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return {'bytes':p.stat().st_size,'sha256':h.hexdigest(),'mtime':p.stat().st_mtime}
try:
 import subprocess
 note('install pinned')
 subprocess.run(['pip','install','-q','git+https://github.com/kunifujiwara/VoxCity.git@'+M['commit'],'trimesh','rtree','xlrd','scikit-image'],check=True,timeout=1200)
 import numpy as np, pandas as pd, geopandas as gpd, requests, trimesh
 from pyproj import CRS,Transformer
 from shapely.ops import transform,polygonize
 from shapely.geometry import Point, Polygon
 from scipy.ndimage import label,distance_transform_edt,binary_erosion
 from scipy.spatial import cKDTree
 from skimage.morphology import skeletonize
 from rasterio.features import rasterize
 from affine import Affine
 from voxcity.generator import get_voxcity
 from voxcity.downloader.osm import load_gdf_from_openstreetmap
 from voxcity.downloader.overture import load_gdf_from_overture
 from voxcity.utils.orientation import AXES
 assert AXES==('north','east','up')
 lat,lon=37.92943,139.05260
 ae=CRS.from_proj4(f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs')
 ll=CRS.from_epsg(4326);forward=Transformer.from_crs(ll,ae,always_xy=True); inverse=Transformer.from_crs(ae,ll,always_xy=True)
 theta=np.deg2rad(-1);c,s=np.cos(theta),np.sin(theta)
 def togeo(x,y):return inverse.transform(c*x-s*y,s*x+c*y)
 def toofficial(x,y):
  e,n=forward.transform(x,y);return c*e+s*n,-s*e+c*n
 rect=[togeo(x,y) for x,y in [(-250,-250),(-250,250),(250,250),(250,-250)]]
 M['rectangle_SW_NW_NE_SE']=rect;M['axis_contract']='v[i=north from south,j=east from west,k=up]';save()
 def rast(geoms,step=.25,half=200):
  n=int(2*half/step)
  a=rasterize([(g,1) for g in geoms if g is not None and not g.is_empty],out_shape=(n,n),transform=Affine(step,0,-half,0,step,-half),dtype='uint8',all_touched=False)
  return a.astype(bool)
 def iou(a,b,disc):
  return float(((a&b)&disc).sum()/max(1,((a|b)&disc).sum()))
 def field(a):
  return {'shape':list(a.shape),'bytes':a.nbytes,'min':int(a.min()),'max':int(a.max()),'solid_cells':int((a==-3).sum())}
 # Sources retrieved in geographic rectangle, but Overture's bounding-box query may include outsiders.
 for source,fetch in [('OpenStreetMap',load_gdf_from_openstreetmap),('Overture',load_gdf_from_overture)]:
  note('fetch',source);ft=time.time()
  if (P/(source+'.gpkg')).exists():g=gpd.read_file(P/(source+'.gpkg'))
  else:
   g=fetch(rect);g.to_file(P/(source+'.gpkg'),driver='GPKG')
  d=M['sources'].get(source,{'rows':len(g),'fetch_seconds':time.time()-ft,'fields':list(g.columns)});M['sources'][source]=d
  if source=='OpenStreetMap':
   d['height_direct']=int((g['height_source']=='explicit').sum()) if 'height_source' in g else None
   d['num_floors_nonnull']=int((g['height_source']=='levels').sum()) if 'height_source' in g else None
  else:
   from overturemaps import core
   bbox=(min(p[0] for p in rect),min(p[1] for p in rect),max(p[0] for p in rect),max(p[1] for p in rect))
   d['raw_topics']={};d['height_direct']=0;d['num_floors_nonnull']=0
   for topic in ('building','building_part'):
    orig=core.geodataframe(topic,bbox=bbox)
    vals={k:int(pd.to_numeric(orig[k],errors='coerce').notna().sum()) if k in orig else 0 for k in ('height','num_floors')}
    d['raw_topics'][topic]={'rows':len(orig),'columns':list(orig.columns),'nonnull':vals}
    d['height_direct']+=vals['height'];d['num_floors_nonnull']+=vals['num_floors']
  d['missing_fraction']=1-d['height_direct']/len(g) if len(g) else None
  note('raw heights',source,d['rows'],d['height_direct'],d['num_floors_nonnull'])
  g_off=g.to_crs(ll).geometry.apply(lambda geom:transform(toofficial,geom) if geom is not None else None)
  # Gate uses exact same source polygons, clipped to official 190m disk.
  upstream=rast(g_off,step=1,half=250)
  ii,jj=np.indices((500,500));disc=np.hypot(jj+.5-250,ii+.5-250)<190
  d['upstream_polygons_count']=int(g_off.notna().sum());save()
  for res in (1,.5):
   key=f'{res:g}m';note('generate',source,key);t=time.time()
   # Per-process peak rather than process-cumulative: fork a subprocess per generation.
   script=P/'one_generation.py'
   script.write_text('''import sys,json,time,resource,numpy as np\nfrom pathlib import Path\nfrom voxcity.generator import get_voxcity\nimport geopandas as gpd\np=Path(sys.argv[1]);src=sys.argv[2];res=float(sys.argv[3]);rect=json.loads(sys.argv[4]);g=gpd.read_file(p/(src+".gpkg"));t=time.monotonic()\nc=get_voxcity(rect,res,building_source=src,building_gdf=g,building_complementary_source="None",land_cover_source="OpenStreetMap",canopy_height_source="Static",dem_source="None",static_tree_height=0,flat_dem=True,gridvis=False,mapvis=False,save_voxcity_data=False,parallel_download=False,output_dir=str(p/(src+"_"+sys.argv[3])))\na=c.voxels.classes;np.save(p/(src+"_"+sys.argv[3]+".npy"),a);np.save(p/(src+"_"+sys.argv[3]+"_height.npy"),c.buildings.heights);print(json.dumps({"seconds":time.monotonic()-t,"peak_rss_kb":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"shape":a.shape,"solid_cells":int((a==-3).sum()),"height_max":float(np.nanmax(c.buildings.heights)),"rectangle_vertices":c.extras.get("rectangle_vertices")}),flush=True)''')
   if not (P/(source+'_'+str(res)+'.npy')).exists():
    z=subprocess.run(['python',str(script),str(P),source,str(res),json.dumps(rect)],capture_output=True,text=True,timeout=1500)
    (P/(source+'_'+key+'.log')).write_text(z.stdout+'\nSTDERR\n'+z.stderr[-15000:])
    if z.returncode:raise RuntimeError(f'{source} {key} generation exit {z.returncode}: {z.stderr[-1500:]}')
    generation=json.loads(z.stdout.strip().splitlines()[-1]); d[key]=generation;d[key]['outer_seconds']=time.time()-t
   a=np.load(P/(source+'_'+str(res)+'.npy'),mmap_mode='r');expected=round(500/res)
   if a.shape[:2] != (expected,expected):raise RuntimeError('grid size mismatch '+str(a.shape))
   d[key]['voxel_field']=digest(P/(source+'_'+str(res)+'.npy'));note('generated',source,key,a.shape,d[key]['peak_rss_kb']);save()
   if res==1:
    solid=np.asarray(a[:,:,2]==-3)
    forms={'id':solid,'flip_i':solid[::-1,:],'flip_j':solid[:,::-1],'flip_both':solid[::-1,::-1],'transpose':solid.T,'transpose_flip_i':solid.T[::-1,:],'transpose_flip_j':solid.T[:,::-1],'transpose_flip_both':solid.T[::-1,::-1]}
    d['gate_iou']={k:iou(v,upstream,disc) for k,v in forms.items()};d['gate_pass']=d['gate_iou']['id']>=.7 and d['gate_iou']['id']>max(v for k,v in d['gate_iou'].items() if k!='id')
    note('GATE',source,d['gate_pass'],d['gate_iou']);save()
    if not d['gate_pass']:
     M['halt']='orientation gate failed; no downstream criteria evaluated';save();raise RuntimeError(M['halt'])
  # Only after both generation and gate: downstream calculations below.
  d['downstream_ready']=True;save()
 note('all sources passed gate')
except Exception as e:
 M['error']=repr(e);M['traceback']=traceback.format_exc();note('ERROR',repr(e))
finally:
 M['end']=time.time();M['elapsed_seconds']=M['end']-M['start'];save();(P/'run.done').write_text(str(time.time()));print('DONE',M.get('error','ok'),flush=True)
