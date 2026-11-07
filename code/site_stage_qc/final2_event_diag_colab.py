"""Complete process-time diagnostic after handling WB2 naive UTC timestamps."""
import csv,json,datetime as dt
from pathlib import Path
root=Path('/content/site_stage_qc/final2');adm=[r for r in csv.DictReader((root/'station_admission.csv').open()) if r['admitted']=='true'];o={(x['station'],x['season_year']):x for x in map(json.loads,(root/'qc_station_seasons.jsonl').read_text().splitlines())};e={x['season_year']:x['stations'] for x in map(json.loads,(root/'era_seasons.jsonl').read_text().splitlines())}
d=[]
for h in adm:
 st=h['station']
 for y in range(2007,2022):
  z=o[st,y]
  if not z['valid']:continue
  stationtime=dt.datetime.fromisoformat(z['qc_peak']['event_utc'].replace('Z','+00:00'))
  eratime=dt.datetime.fromisoformat(e[y][st]['max_utc'].replace('Z','+00:00'))
  if eratime.tzinfo is None:eratime=eratime.replace(tzinfo=dt.timezone.utc)
  dh=abs((stationtime-eratime).total_seconds())/3600
  d.append({'station':st,'region':h['region'],'season_year':y,'station_peak_utc':stationtime.isoformat(),'era_peak_utc':eratime.isoformat(),'hours_apart':dh,'within_36h':str(dh<=36).lower(),'station_peak_kn':z['qc_peak']['kn'],'era_season_max_mps':e[y][st]['ace1_max_mps'],'ratio_kn_per_mps':z['qc_peak']['kn']/e[y][st]['ace1_max_mps']})
with (root/'event_diagnostic.csv').open('x',newline='') as f:w=csv.DictWriter(f,list(d[0]));w.writeheader();w.writerows(d)
print('EVENT_36H',sum(x['within_36h']=='true' for x in d),len(d))
