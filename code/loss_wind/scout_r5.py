"""Small annotation-only survey of candidate hurricane views, no imagery."""
import requests, collections, statistics
from pathlib import Path
P=Path(__file__).resolve().parent
rev='c3f5421e1167bb7e88a765e3afa38bebd9898479'
base=f'https://huggingface.co/datasets/CRASAR/CRASAR-U-DROIDs/resolve/{rev}/'
paths=[
 'train/annotations/CREWED/building_damage_assessment/1001-Harlem-Heights.geo.tif_20220930d_RGB.geo.tif.json',
 'train/annotations/CREWED/building_damage_assessment/1001-McGregor-College-Pkwy-South.1.geo.tif_20220930d_RGB.geo.tif.json',
 'train/annotations/CREWED/building_damage_assessment/1001-McGregor-College-Pkwy-South.2.geo.tif_20220930d_RGB.geo.tif.json',
 'train/annotations/CREWED/building_damage_assessment/1001-Summerlin-San-Carlos.geo.tif_20220930d_RGB.geo.tif.json',
 'test/annotations/CREWED/building_damage_assessment/20230831-Jena-SteinhatcheeRiverSouth.geo.tif_20230831a_RGB.geo.tif.json',
 'train/annotations/CREWED/building_damage_assessment/20210831-LA-DIV-01.geo.tif_20210831a_RGB.geo.tif.json']
for path in paths:
 r=requests.get(base+path,timeout=90);r.raise_for_status();a=r.json()
 lat=[sum(p['lat'] for p in x['EPSG:4326'])/len(x['EPSG:4326']) for x in a if x.get('EPSG:4326')]
 lon=[sum(p['lon'] for p in x['EPSG:4326'])/len(x['EPSG:4326']) for x in a if x.get('EPSG:4326')]
 print(path,'bytes',len(r.content),'N',len(a),'ids',len({x['building_id'] for x in a}),'labels',dict(collections.Counter(x['label'] for x in a)),'latlon extent',(round(min(lat),4),round(max(lat),4),round(min(lon),4),round(max(lon),4)) if lat else None,flush=True)
 (P/('r5_raw_'+path.split('/')[-1])).write_bytes(r.content)
