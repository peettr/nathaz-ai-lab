#!/usr/bin/env python3
"""Station-year retrieval accounting; shared account CU cannot be assigned."""
import csv,gzip,json,tarfile,collections
from pathlib import Path
root=Path(__file__).resolve().parent
meta=json.loads((root/'forecast_meta_summary.json').read_text())
old=json.loads((root/'../asos_2023_20261014/station_year_ledger.json').read_text())['station_year']
stations=[r['station'] for r in csv.DictReader((root/'stations.csv').open())]
with tarfile.open(root/'partial_station_data.tar.gz') as tar:
 obs=collections.Counter();secs=0;obytes=0
 for m in tar:
  if m.name.startswith('metar/metar_2022_') and m.name.endswith('.json'):
   x=json.load(tar.extractfile(m));secs+=x['seconds'];obytes+=x['response_bytes'];obs.update(x['station_counts'])
rows=[]
for s in stations:
 rows.append({'station':s,'year':2022,'observation_hours':obs[s],
              'forecast_objects_by_source':{k:v['objects'] for k,v in meta.items()},
              'forecast_rows_by_source':{k:v['station_rows'] for k,v in meta.items()},
              'retrieval_fetch_seconds_shared_all_stations':sum(v['shared_fetch_seconds'] for v in meta.values())+secs,
              'gfs_range_bytes_shared_all_stations':meta['GFS']['gfs_range_bytes_shared'],
              'metar_response_bytes_shared_all_stations':obytes,'aiwp_range_bytes':None,
              'station_csv_bytes_shared_all_stations':sum(v['station_csv_bytes_shared'] for v in meta.values()),
              'CU':None,'CU_note':'Account shared with other Colab sessions; no defensible station-year CU attribution. Account delta reported separately in run audit.'})
for x in old:
 rows.append({'station':x['station'],'year':2023,'observation_hours':x['observed_hourly_rows'],
              'reused_preliminary_station_rows':x['paired_rows'], 'reused_preliminary_station_csv_bytes':x['station_csv_bytes'],
              'retrieval_seconds_equal_share_from_prior_run':x['retrieval_wall_seconds_allocated_equal_station_share'],
              'CU':None,'CU_note':'Reused 2023 series; prior account concurrent and CU non-attributable.'})
(root/'station_year_ledger_final.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
print('STATION_YEAR_LEDGER',len(rows),sum(x.get('observation_hours',0) for x in rows))
