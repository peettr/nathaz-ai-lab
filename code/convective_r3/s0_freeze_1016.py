"""Freeze S0 CSVs after exact paired checkpoint; append immutable hashes before S1."""
import csv,datetime as dt,hashlib,json,pathlib,collections,sys
R=pathlib.Path(__file__).parent
eli=json.loads((R/'s0_eligible_1016.json').read_text());sel=json.loads((R/'s0_selected_provisional_1016.json').read_text());pairs=json.loads((R/'s0_pair_progress_terminal_1016.json').read_text());assert pairs['index']==len(sel)==200
byid={x['id']:x for x in sel}; controls=pairs['paired'];unpaired=set(pairs['unpaired']);assert len(controls)+len(unpaired)==200
assert len({x['event_id'] for x in controls})==len(controls);assert set(byid)=={x['event_id'] for x in controls}|unpaired
assert len({(x['station'],x['utc'][:10]) for x in controls})==len(controls)
assert not unpaired, 'same-climate-region fallback not exhausted for unpaired events; do not freeze yet'
eventdays={x['hit']['utc'][:10] for x in eli};assert all(x['utc'][:10] not in eventdays for x in controls)
for group,count,cap in [('v1',301,120),('conus',132,80)]:
 assert sum(x['group']==group for x in eli)==count;assert sum(x['group']==group for x in sel)==cap
fields=['group','id','station','utc','obs_kt','lat','lon','state','year','ncei_url','ncei_version','iem_url','radar_url','radar_40','radar_35','grid_edge_km','matched_control','metar']
with (R/'events_r3.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for x in sel:
  w.writerow(dict(group=x['group'],id=x['id'],station=x['station'],utc=x['hit']['utc'],obs_kt=x['hit']['kt'],lat=x['lat'],lon=x['lon'],state=x['state'],year=x['hit']['utc'][:4],ncei_url=x['ncei_url'],ncei_version=x['ncei_url'].split('_c')[-1].split('.')[0],iem_url=x['iem_url'],radar_url=x['radar_evidence_url'],radar_40=x['radar_40'],radar_35=x['radar_35'],grid_edge_km=x['grid_edge_km'],matched_control=x['id'] not in unpaired,metar=x['hit']['metar']))
cf=['group','event_id','station','utc','max_kt','lat','lon','state','year','ncei_no_report_url','ncei_version','iem_url','radar_url','network_url','day_gap','phase','metar']
with (R/'controls_r3.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=cf);w.writeheader()
 for x in controls:
  event=byid[x['event_id']];w.writerow(dict(group=event['group'],event_id=x['event_id'],station=x['station'],utc=x['utc'],max_kt=x['max_kt'],lat=x['lat'],lon=x['lon'],state=x['state'],year=x['utc'][:4],ncei_no_report_url=x['ncei_url'],ncei_version=x['ncei_url'].split('_c')[-1].split('.')[0],iem_url=x['iem_url'],radar_url=x['radar_url'],network_url=x['network_url'],day_gap=x['day_gap'],phase=x['phase'],metar=x['metar']))
sha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'events_r3.csv',R/'controls_r3.csv')}
log=R/'FROZEN_SHA256.txt'
with log.open('a') as f:
 for name,hashval in sha.items():f.write(f"{dt.datetime.now().astimezone().strftime('%m-%d %H:%M %Z')} 样本清单冻结 {hashval}  06_Logs/convective_r3/{name}\n")
print('FROZEN',sha,'pair count',collections.Counter(byid[x['event_id']]['group'] for x in controls),'unpaired',len(unpaired))
