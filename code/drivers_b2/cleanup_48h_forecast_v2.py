#!/usr/bin/env python3
"""Approved 48h-cycle forecast GRIB cleanup after verified GFS WPS readback."""
import hashlib, json, pathlib, re, subprocess, sys
R=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
I=R/'inputs_N8N9N10_v1'
event,stamp=sys.argv[1:]
assert (event,stamp) in {('N8','2024052206'),('N9','2022060806')}
lead='48h'
ledger=I/f'FORECAST_GRIB_CLEANUP_{event}_48_20261125_v2.json'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
if ledger.exists():raise FileExistsError(ledger)
ops=R/f'drivers_{event}_v1'/f'ops_{event}_{lead}_GFS_b2'
assert (ops/'exitcode').read_text().strip()=='0'
rows=json.loads((ops/f'WPS_{stamp}_GFS_REPORT.json').read_text())
assert len(rows)==11,len(rows)
for row in rows:
 p=R/f'drivers_{event}_v1'/row['file']
 assert row['records']==172 and row['arm']=='GFS' and row['cycle']==stamp
 assert sha(p)==row['sha256'],p
assert (I/f'input_{stamp}_zero.nc').is_file()
gate={r['key']:r for r in map(json.loads,(I/f'INPUT_GATE_{event}_{lead}_{stamp}_v3.jsonl').read_text().splitlines())}
assert json.loads((I/f'INPUT_GATE_{event}_{lead}_{stamp}_v3_SUMMARY.json').read_text())['all_pass']
files=[]
for p in sorted((I/'raw'/stamp).iterdir()):
 m=re.fullmatch(r'gfs\.0p25(b?)\.(\d{10})\.f(\d{3})\.grib2',p.name)
 if not m or m.group(2)!=stamp or int(m.group(3))<6:continue
 key=f'd08400{3 if m.group(1) else 1}_{stamp}_f{m.group(3)}'
 source=gate[key]
 assert p.stat().st_size==source['bytes'] and sha(p)==source['sha256'],p
 files.append({'path':str(p),'bytes':source['bytes'],'sha256':source['sha256'],'url':source['url']})
assert len(files)==10,len(files)
payload={'cycle':stamp,'scope':'same-cycle f006+ only; t0/prior analyses and NetCDF retained','files':files,'status':'validated_before_delete'}
with ledger.open('x') as f:json.dump(payload,f,indent=2);f.write('\n')
for x in files:pathlib.Path(x['path']).unlink()
payload['status']='deleted';payload['deleted_bytes']=sum(x['bytes'] for x in files)
payload['df_after']=subprocess.check_output(['df','-B1','/groups/kareem'],text=True).strip()
with ledger.open('w') as f:json.dump(payload,f,indent=2);f.write('\n')
print(json.dumps({'ledger':str(ledger),'count':len(files),'deleted_bytes':payload['deleted_bytes'],'df_after':payload['df_after']}))
