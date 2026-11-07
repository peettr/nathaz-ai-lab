#!/usr/bin/env python3
"""Summarize exact 2022 station-only objects, no global HDF5 size as transfer bytes."""
import collections,json,glob,os
from pathlib import Path
root=Path('/content/a1/partial_forecasts/2022')
selected={'FOUR_v200_GFS','PANG_v100_GFS','GRAP_v100_GFS','GFS'}
summary=collections.defaultdict(lambda:{'objects':0,'station_rows':0,'shared_fetch_seconds':0.,'gfs_range_bytes_shared':0,'station_csv_bytes_shared':0,'aiwp_range_bytes':None})
for path in root.glob('*/*.json'):
 m=json.loads(path.read_text());s=m['source']
 if s not in selected or int(m['init'][8:10])>15:continue
 v=summary[s];v['objects']+=1;v['station_rows']+=2
 v['shared_fetch_seconds']+=m['seconds'];v['station_csv_bytes_shared']+=m.get('csv_bytes',path.with_suffix('.csv').stat().st_size)
 if s=='GFS':v['gfs_range_bytes_shared']+=m.get('source_object_bytes_or_gfs_range_bytes',m.get('object_size_or_gfs_transferred_bytes',0))
assert all(x['objects']==360 and x['station_rows']>=720 for x in summary.values()),summary
Path('/content/a1/forecast_meta_summary.json').write_text(json.dumps(summary,indent=2))
print('LEDGER',dict(summary))
