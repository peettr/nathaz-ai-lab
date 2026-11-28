"""Prepare small CRASAR label cohort with 3DEP elevation and NHC forecast surge screen."""
import json,requests,zipfile,io,collections,math
from pathlib import Path
import numpy as np,rasterio
from rasterio.io import MemoryFile
from rasterio.warp import transform as crs_transform
P=Path(__file__).resolve().parent
FILES={'ian_harlem':'r5_raw_1001-Harlem-Heights.geo.tif_20220930d_RGB.geo.tif.json','ian_mcgregor':'r5_raw_1001-McGregor-College-Pkwy-South.1.geo.tif_20220930d_RGB.geo.tif.json','ian_summerlin':'r5_raw_1001-Summerlin-San-Carlos.geo.tif_20220930d_RGB.geo.tif.json','idalia_jena':'r5_raw_20230831-Jena-SteinhatcheeRiverSouth.geo.tif_20230831a_RGB.geo.tif.json'}
# NHC product is prospective (not observed flood). Do not interpret outside raster as flood-free.
url='https://www.nhc.noaa.gov/gis/inundation/forecasts/AL0922_27_inundation.zip'
z=zipfile.ZipFile(io.BytesIO(requests.get(url,timeout=120).content))
raw=z.read(next(x for x in z.namelist() if x.endswith('.tif')))
(P/'r5_nhc_ian_adv27_forecast_inundation.tif').write_bytes(raw)
allrows=[]
with rasterio.open(P/'r5_nhc_ian_adv27_forecast_inundation.tif') as flood:
 for area,f in FILES.items():
  a=json.loads((P/f).read_text());coords=[];rows=[]
  for x in a:
   pts=x.get('EPSG:4326') or []
   if not pts:continue
   lat=sum(v['lat'] for v in pts)/len(pts);lon=sum(v['lon'] for v in pts)/len(pts)
   rows.append({'area':area,'event':area.split('_')[0].upper(),'building_id':x['building_id'],'view_id':x['view_id'],'label':x['label'],'lat':lat,'lon':lon,'source_file':f})
  # 3DEP clipped 10-15 m raster: bare-earth, 2026 service vintage is post-event.
  lo=min(r['lon'] for r in rows)-.001;hi=max(r['lon'] for r in rows)+.001;la=min(r['lat'] for r in rows)-.001;ha=max(r['lat'] for r in rows)+.001
  size=f'{math.ceil((hi-lo)*10000)},{math.ceil((ha-la)*10000)}'
  u='https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage'
  response=requests.get(u,params={'f':'json','bbox':f'{lo},{la},{hi},{ha}','bboxSR':4326,'imageSR':4326,'size':size,'format':'tiff','pixelType':'F32'},timeout=90);response.raise_for_status();j=response.json();assert 'href' in j,j
  rr=requests.get(j['href'],timeout=90);rr.raise_for_status();dem=P/f'r5_3dep_{area}.tif';dem.write_bytes(rr.content)
  with rasterio.open(dem) as ds:
   el=list(ds.sample([(r['lon'],r['lat']) for r in rows]));print('DEM',area,ds.crs,ds.bounds,'minmax',np.nanmin([v[0] for v in el]),np.nanmax([v[0] for v in el]),flush=True)
  for r,v in zip(rows,el):r['elevation_m_3dep']=float(v[0])
  if area.startswith('ian'):
   xf,yf=crs_transform('EPSG:4326',flood.crs,[r['lon'] for r in rows],[r['lat'] for r in rows]);vals=list(flood.sample(zip(xf,yf)))
   for r,v in zip(rows,vals):r['nhc_forecast_inundation_class']=int(v[0])
  else:
   for r in rows:r['nhc_forecast_inundation_class']=None
  print(area,'N',len(rows),'elev quantiles',np.quantile([r['elevation_m_3dep'] for r in rows],[0,.1,.5,.9,1]).round(2),'forecast',collections.Counter(r['nhc_forecast_inundation_class'] for r in rows),flush=True)
  allrows+=rows
(P/'r5_prepared_labels.json').write_text(json.dumps(allrows,indent=1))
print('TOTAL',len(allrows))
