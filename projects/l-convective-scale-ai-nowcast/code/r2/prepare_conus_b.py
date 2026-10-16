"""Freeze CONUS 12 events + 6 checked controls, normalize immutable pilot rows."""
import csv,json,pathlib,os
R=pathlib.Path(__file__).parent;D=R/'segment_b_20261015';D.mkdir(exist_ok=True)
events=[x for x in csv.DictReader((R/'events_r2_verified.csv').open()) if x['group']=='conus'];controls=list(csv.DictReader((D/'controls_conus_verified.csv').open()))
assert len(events)==12 and len(controls)==6
ordered=[]
for n in range(6):ordered.extend(events[n*2:n*2+2]+[controls[n]])
manifest=D/'segment_b_manifest.csv'
with manifest.open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['group','id','station','utc','obs_kt','lat','lon','ncei_url','iem_url']);w.writeheader();w.writerows({k:x[k] for k in w.fieldnames} for x in ordered)
orig=[json.loads(s) for s in (R/'conus_pilot_final.jsonl').read_text().splitlines()];hr=json.loads((R/'conus_hrrr_pilot.json').read_text());e=next(x for x in events if x['id']=='1329296')
assert len(orig)==10 and {x['seed'] for x in orig}==set(range(101,111))
base=dict(id=e['id'],group='conus',station=e['station'],obs_kt=float(e['obs_kt']),peak_utc=e['utc'],init=hr['init'],lead_h=1,condition='ARCO_ERA5',ncei_url=e['ncei_url'],iem_url=e['iem_url'],status='ok',pilot_origin='r2/conus_pilot_final.jsonl')
out=[]
for row in orig:
 r={**base,'source':'conus','seed':row['seed'],'wide':row['wide'],'narrow':row['narrow'],'runtime_sec':row['runtime_s'],'gpu_peak_gb':row['gpu_peak_gb']};out.append(r)
h={**base,'source':'hrrr','seed':None,'wide':{'gust':hr['wide_gust'],'speed10':hr['wide_speed10']},'narrow':{'gust':hr['narrow_gust'],'speed10':hr['narrow_speed10']},'runtime_sec':None,'pilot_origin':'r2/conus_hrrr_pilot.json'};out.append(h)
checkpoint=D/'checkpoint_start_pilot11.jsonl'
with checkpoint.open('x') as f:
 for r in out:f.write(json.dumps(r)+'\n')
print('MANIFEST',manifest,len(ordered),'PILOT',checkpoint,len(out))
