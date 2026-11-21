#!/usr/bin/env python3
"""Audit immutable partial Colab archive; no scientific scoring."""
import json,csv,tarfile,collections,io
from pathlib import Path
root=Path(__file__).resolve().parent
archive=root/'partial_station_data.tar.gz'
rows=collections.defaultdict(lambda:{'observation_hours':0,'observation_fetch_seconds_shared':0.,'observation_response_bytes_shared':0,'forecast_station_rows':0,'forecast_object_count':0,'forecast_fetch_seconds_shared':0.,'forecast_gfs_range_bytes_shared':0})
with tarfile.open(archive,'r:gz') as tar:
 for member in tar:
  if not member.isfile():continue
  if member.name.startswith('metar/') and member.name.endswith('.json'):
   o=json.load(tar.extractfile(member));counts=o['station_counts']
   for station,n in counts.items():
    r=rows[(station,o['year'])];r['observation_hours']+=n;r['observation_fetch_seconds_shared']+=o['seconds'];r['observation_response_bytes_shared']+=o['response_bytes']
  if member.name.startswith('partial_forecasts/') and member.name.endswith('.json'):
   o=json.load(tar.extractfile(member));year=int(o['init'][:4]);source=o['source'];n=o['station_rows']//12
   # 6 lead rows at each of the 12 station points.
   assert n==6
   for station in csv.DictReader((root/'stations.csv').open()):
    r=rows[(station['station'],year)];r['forecast_station_rows']+=6;r['forecast_object_count']+=1;r['forecast_fetch_seconds_shared']+=o['seconds']
    if source=='GFS':r['forecast_gfs_range_bytes_shared']+=o['object_size_or_gfs_transferred_bytes']
output=[]
for (station,year),item in sorted(rows.items()):
 d={'station':station,'year':year,**item,'colab_cu_per_station_year':None,'aiwp_actual_range_bytes':None,'notes':'Fetch time and response bytes are shared per station group, not station-attributable; GFS bytes also shared; account CU concurrent and non-attributable.'}
 output.append(d)
(root/'station_year_partial_ledger.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
print('LEDGER_DONE',len(output),'station-years',sum(r['observation_hours'] for r in output),'METAR hourly rows',sum(r['forecast_station_rows'] for r in output),'forecast station rows')
