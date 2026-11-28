import os,sys,json,time,subprocess,traceback
from pathlib import Path
root=Path('/content/qtl_l2630_step1a');root.mkdir(exist_ok=True)
start=time.time()
def log(*x):print(time.strftime('%Y-%m-%d %H:%M:%S'),*x,flush=True)
try:
 log('install pinned BRAILS++')
 subprocess.run(['/usr/local/bin/uv','pip','install','--python',sys.executable,'git+https://github.com/NHERI-SimCenter/BrailsPlusPlus.git@3369ee4dbdda','mapbox-earcut','trimesh','geopandas','pyproj'],check=True)
 from brails import Importer
 from pyproj import Geod
 from shapely.geometry import Polygon
 imp=Importer();RegionBoundary=imp.get_class('RegionBoundary');Scraper=imp.get_class('USA_FootprintScraper')
 geod=Geod(ellps='WGS84')
 candidates={'Detroit Midtown':(42.3550,-83.0640),'Philadelphia Center City':(39.9526,-75.1636),'Chicago Near North':(41.8988,-87.6378)}
 result={}
 for name,(lat,lon) in candidates.items():
  try:
   west=geod.fwd(lon,lat,270,250)[0];east=geod.fwd(lon,lat,90,250)[0];south=geod.fwd(lon,lat,180,250)[1];north=geod.fwd(lon,lat,0,250)[1]
   region=RegionBoundary({'type':'locationPolygon','data':(west,south,east,north)})
   log('candidate',name,'bbox',west,south,east,north)
   inv=Scraper({'length':'m'}).get_footprints(region)
   p=root/('candidate_'+name.lower().replace(' ','_')+'.geojson');inv.write_to_geojson(p)
   data=json.loads(p.read_text());ft=data['features'];heights=[x['properties'].get('buildingheight') for x in ft]
   valid=[x is not None and isinstance(x,(int,float)) and x>0 for x in heights]
   result[name]={'count':len(ft),'valid':sum(valid),'coverage':sum(valid)/len(ft) if ft else None,'bbox':[west,south,east,north],'file':str(p),'seconds':round(time.time()-start,1)}
   log('result',name,result[name])
  except Exception as e:result[name]={'error':repr(e)};log('candidate error',name,repr(e))
 (root/'candidates.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));log('done',result)
 (root/'candidate.done').write_text('ok')
except Exception:
 traceback.print_exc();(root/'candidate.failed').write_text(traceback.format_exc());raise
