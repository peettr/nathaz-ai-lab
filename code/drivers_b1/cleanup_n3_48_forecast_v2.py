#!/usr/bin/env python3
"""Approved N3 48h forecast-only GRIB cleanup; fail closed and keep evidence."""
import hashlib, json, pathlib, re, subprocess, sys
R=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
I=R/'inputs_N1N3N4_v1'; stamp='2022070318'
ledger=I/'FORECAST_GRIB_CLEANUP_N3_48_20261124_v2.json'
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(4*1024*1024),b''): h.update(block)
 return h.hexdigest()
if ledger.exists(): raise FileExistsError(ledger)
ops=R/'drivers_N3_v1/ops_N3_48h_GFS_b1'
assert (ops/'exitcode').read_text().strip()=='0'
reports=json.loads((ops/f'WPS_{stamp}_GFS_REPORT.json').read_text())
assert len(reports)==10
for row in reports:
 p=R/'drivers_N3_v1'/row['file']
 assert row['records']==172 and row['arm']=='GFS' and row['cycle']==stamp
 assert sha(p)==row['sha256'],p
raw=I/'raw'/stamp
assert (I/f'input_{stamp}_zero.nc').is_file()
gate={r['key']:r for r in map(json.loads,(I/f'INPUT_GATE_N3_48h_{stamp}_v4.jsonl').read_text().splitlines())}
assert json.loads((I/f'INPUT_GATE_N3_48h_{stamp}_v4_SUMMARY.json').read_text())['all_pass']
rows=[]
for p in sorted(raw.iterdir()):
 m=re.fullmatch(r'gfs\.0p25(b?)\.(\d{10})\.f(\d{3})\.grib2',p.name)
 if not m or m.group(2)!=stamp or int(m.group(3))<6:continue
 key=f'd08400{3 if m.group(1) else 1}_{stamp}_f{m.group(3)}'
 source=gate[key]
 assert p.stat().st_size==source['bytes'] and sha(p)==source['sha256'],p
 rows.append({'path':str(p),'bytes':source['bytes'],'sha256':source['sha256'],'url':source['url']})
assert len(rows)==9,(len(rows),rows)
payload={'cycle':stamp,'scope':'same-cycle f006+ only, retain t0 and t-6h analyses plus NetCDF','files':rows,'approved':True,'status':'validated_before_delete'}
with ledger.open('x') as f: json.dump(payload,f,indent=2);f.write('\n')
for row in rows:
 pathlib.Path(row['path']).unlink()
payload['status']='deleted'; payload['deleted_bytes']=sum(r['bytes'] for r in rows)
payload['df_after']=subprocess.check_output(['df','-B1','/groups/kareem'],text=True).strip()
with ledger.open('w') as f:json.dump(payload,f,indent=2);f.write('\n')
print(json.dumps({'ledger':str(ledger),'count':len(rows),'deleted_bytes':payload['deleted_bytes'],'df_after':payload['df_after']},ensure_ascii=False))
