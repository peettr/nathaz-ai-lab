import csv,json,math
from pathlib import Path
from collections import Counter
r=Path('/content/sens4');s=Path('/content/sens2')
rows=list(csv.DictReader((r/'gev_lmom_sensitivity.csv').open()));fits=json.loads((r/'gev_fits.json').read_text());loso={v['station']:v for v in csv.DictReader((r/'loso_results.csv').open())}
for row in rows:
 st=row['station'];train=json.loads(loso[st]['train_stations']);actual=fits[st]['station']['x10'];base=sum(fits[q]['station']['x10'] for q in train)/len(train);row['R10_base']=base/actual
assert len(rows)==29 and all(row.get('R10') and math.isfinite(float(row['R10_base'])) for row in rows)
with (r/'gev_with_baseline.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
gev={'mapped_hit':sum(abs(float(x['R10'])-1)<=.15 for x in rows),'baseline_hit':sum(abs(float(x['R10_base'])-1)<=.15 for x in rows),'regional':{g:{'mapped':sum(abs(float(x['R10'])-1)<=.15 for x in rows if x['region']==g),'baseline':sum(abs(float(x['R10_base'])-1)<=.15 for x in rows if x['region']==g)} for g in ('plains','other')}}
(r/'gev_counts.json').write_text(json.dumps(gev,indent=2))
old=list(csv.DictReader((s/'final2_station_params.csv').open()));new=list(csv.DictReader((r/'station_params.csv').open()));a={x['station']:x for x in old}
change=[]
for x in new:
 y=a[x['station']];p=float(y['station_x10_kn']);q=float(x['station_x10_kn']);change.append({'station':x['station'],'region':x['region'],'final2_x10_kn':p,'sensitivity_x10_kn':q,'delta_kn':q-p,'delta_pct_of_final2':100*(q/p-1)})
with (r/'x10_changes.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,change[0].keys());w.writeheader();w.writerows(change)
changed=json.loads((r/'changed_seasons.json').read_text());print('SUMMARY',json.dumps({'changed_seasons':len(changed),'changed_stations':len({z['station'] for z in changed}),'gev':gev,'new_isd_requests':len(json.loads((s/'new_isd_requests.json').read_text())) if (s/'new_isd_requests.json').exists() else 0}),flush=True)
