#!/usr/bin/env python3
"""Approved N9 72h f006+ GRIB cleanup after GFS WPS hash readback."""
import hashlib, json, pathlib, re, subprocess
R=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
I=R/'inputs_N8N9N10_v1'
cycle='2022060706'
ledger=I/'FORECAST_GRIB_CLEANUP_N9_72_20261125_v1.json'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
assert not ledger.exists(),ledger
ops=R/'drivers_N9_v1/ops_N9_72h_GFS_b2'
assert (ops/'exitcode').read_text().strip()=='0'
rows=json.loads((ops/f'WPS_{cycle}_GFS_REPORT.json').read_text())
assert len(rows)==15 and [r['lead'] for r in rows]==list(range(0,85,6))
for row in rows:
 p=R/'drivers_N9_v1'/row['file']
 assert row['records']==172 and row['arm']=='GFS' and row['cycle']==cycle
 assert sha(p)==row['sha256'],p
assert (I/f'input_{cycle}_zero.nc').is_file()
gate={r['key']:r for r in map(json.loads,(I/f'INPUT_GATE_N9_72h_{cycle}_v5.jsonl').read_text().splitlines())}
assert json.loads((I/f'INPUT_GATE_N9_72h_{cycle}_v5_SUMMARY.json').read_text())['all_pass']
files=[]
for p in sorted((I/'raw'/cycle).iterdir()):
 m=re.fullmatch(r'gfs\.0p25(b?)\.(\d{10})\.f(\d{3})\.grib2',p.name)
 if not m or m.group(2)!=cycle or int(m.group(3))<6:continue
 key=f'd08400{3 if m.group(1) else 1}_{cycle}_f{m.group(3)}'
 source=gate[key]
 assert p.stat().st_size==source['bytes'] and sha(p)==source['sha256'],p
 files.append({'path':str(p),'bytes':source['bytes'],'sha256':source['sha256'],'url':source['url']})
assert len(files)==14,len(files)
payload={'cycle':cycle,'scope':'same-cycle f006+ only; t0/prior analyses and NetCDF retained','files':files,'status':'validated_before_delete'}
with ledger.open('x') as f:json.dump(payload,f,indent=2);f.write('\n')
for x in files:pathlib.Path(x['path']).unlink()
payload['status']='deleted';payload['deleted_bytes']=sum(x['bytes'] for x in files)
payload['df_after']=subprocess.check_output(['df','-B1','/groups/kareem'],text=True).strip()
with ledger.open('w') as f:json.dump(payload,f,indent=2);f.write('\n')
print(json.dumps({'ledger':str(ledger),'count':len(files),'deleted_bytes':payload['deleted_bytes'],'df_after':payload['df_after']}))
