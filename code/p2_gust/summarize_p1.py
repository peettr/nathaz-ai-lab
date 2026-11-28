#!/usr/bin/env python3
"""Blind P1 availability/completeness audit, no model-vs-observation scores."""
import csv, gzip, json, hashlib, collections, datetime as dt
from pathlib import Path
R=Path(__file__).resolve().parent
read=lambda n: json.loads((R/n).read_text())
freeze=read('freeze_manifest.json'); pairs=read('pair_manifest_final.json')
stations=list(csv.DictReader((R/'stations_p2_frozen.csv').open()))
assert len(stations)==freeze['selected']==37
assert hashlib.sha256((R/'stations_p2_frozen.csv').read_bytes()).hexdigest()==freeze['station_sha256']==pairs['station_sha256']
g=R/'pairs_p2.csv.gz';h=hashlib.sha256();n=0
with gzip.open(g,'rb') as f:
    while b:=f.read(1024*1024):h.update(b);n+=len(b)
assert h.hexdigest()==pairs['pairs_sha256'] and n==pairs['pairs_bytes']
season_ranges=[('2022-10-01','2023-03-31'),('2023-10-01','2024-03-31'),('2024-10-01','2025-03-31')]
def season(stamp):
    day=stamp[:10]
    return next((i+1 for i,(a,b) in enumerate(season_ranges) if a<=day<=b),None)
avail=collections.defaultdict(lambda:collections.Counter())
for line in (R/'archive_availability.jsonl').open():
    x=json.loads(line);s=season(x['init_utc']);avail[(x['source'],s)][str(x['status'])]+=1
oscar=list(csv.DictReader((R/'oscar_height_metadata.csv').open()))
assert len(oscar)==len(stations)
osc=collections.Counter(x['status'] for x in oscar)
issues=[];status=collections.defaultdict(collections.Counter)
for file,srcdefault in [('forecast_progress_final.jsonl',None),('gfs_progress_final.jsonl','GFS')]:
    for line in (R/file).open():
        x=json.loads(line);src=x.get('source',srcdefault);s=season(x['init'][:4]+'-'+x['init'][4:6]+'-'+x['init'][6:8]);status[src,s][x['status']]+=1
        if x['status']=='error':issues.append((src,x['init'],str(x['seconds_or_error'])[-300:]))
# Join produces one station/source/lead row per in-season valid time. Count only availability of separate fields,
# never calculate residuals, threshold exceedances or skill.
c=collections.defaultdict(collections.Counter);missing_fields=collections.Counter();bad_rows=[]
with gzip.open(g,'rt',newline='') as f:
    reader=csv.DictReader(f)
    for row in reader:
        key=(row['source'],int(row['season']))
        c[key]['rows']+=1
        if row['obs_6x10min_complete']=='1':c[key]['obs_complete']+=1
        if row['fc_u10_ms'] and row['fc_v10_ms']:c[key]['uv10']+=1
        if row['fc_u100_ms'] and row['fc_v100_ms']:c[key]['uv100']+=1
        if row['fc_gust_ms']:c[key]['gust']+=1
        if row['m5_v1_ms'] and row['m5_z_model_sfc_m'] and row['m5_delta_z_m']:c[key]['m5']+=1
        if row['fc_u10_ms'] and row['fc_v10_ms'] and row['obs_6x10min_complete']=='1':c[key]['paired_uv10_obs']+=1
        if row['fc_gust_ms'] and row['obs_6x10min_complete']=='1':c[key]['paired_gust_obs']+=1
        if row['source']=='GFS' and row['fc_u10_ms'] and not row['fc_gust_ms']:bad_rows.append((row['init_utc'],row['lead_h'],row['station']))
assert len(bad_rows)==0
assert all(v['rows']>0 for v in c.values())
obs_counts=pairs['obs_six_complete_station_season'];per_obs=collections.Counter()
for key,val in obs_counts.items():per_obs[int(key.rsplit(':',1)[1])]+=val
print(json.dumps({'station_count':len(stations),'selected':freeze['counts'],'oscar':dict(osc),'availability':{str(k):dict(v) for k,v in avail.items()},'status':{str(k):dict(v) for k,v in status.items()},'issues':issues,'pairs_rows':sum(v['rows'] for v in c.values()),'obs_station_season_sum':dict(per_obs),'field_counts':{str(k):dict(v) for k,v in c.items()},'archive_sha256':hashlib.sha256(g.read_bytes()).hexdigest()},indent=2,ensure_ascii=False))
