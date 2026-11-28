from pathlib import Path
import json,pandas as pd
r=Path('/content/paris_a1_v2');p=r/'parts';records=[];errors=[]
for s in ['FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS','GFS']:
 for f in (p/s).glob('*.json'):records.append(json.loads(f.read_text()))
 for f in (p/s).glob('*.error'):errors.append({'source':s,'file':f.name,'reason':f.read_text().splitlines()[-1]})
summary={}
for s in ['FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS','GFS']:
 g=[x for x in records if x['source']==s]
 summary[s]={'objects':len(g),'station_rows':sum(x['station_rows'] for x in g),'read_seconds_sum_not_wallclock':round(sum(x['seconds'] for x in g),1),'source_object_size_sum_NOT_transferred_bytes':sum(x.get('source_object_bytes_or_ranges') or 0 for x in g) if s!='GFS' else None,'gfs_idx_and_range_response_bytes':sum(x.get('source_object_bytes_or_ranges') or 0 for x in g) if s=='GFS' else None}
meta={'by_source':summary,'errors':errors,'wallclock_seconds':json.loads((r/'forecast_progress.json').read_text())['seconds'],'observation_files':{f.name:{'bytes':f.stat().st_size,'station_hour_rows':sum(1 for _ in open(f))-1} for f in sorted(r.glob('obs_*.csv'))},'unit_account_shared':'Per-task CU cannot be assigned from shared-account balance; CPU VM, other simultaneous sessions.','data_retained':'only station-level CSV downloaded to 工作站; global chunks processed transiently on Colab'}
(r/'audit.json').write_text(json.dumps(meta,indent=2));print('AUDIT',json.dumps({'source_counts':summary,'errors':errors,'wallclock_seconds':meta['wallclock_seconds']}),flush=True)
