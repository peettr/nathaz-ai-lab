#!/usr/bin/env python3
"""Verified, authorized 72h GRIB cleanup; --check is read-only."""
import sys, pathlib, json, hashlib, datetime as dt, subprocess, re
R=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
I=R/'inputs_N8N9N10_v1'
assert sys.argv[1] in ('--check','--execute')
mode=sys.argv[1]
ledger=I/'PAIR_READBACK_GRIB_CLEANUP_72_20261126_v1.json'
assert not ledger.exists(),ledger
cfg=json.loads((I/'event_times_bbox_gc37x.json').read_text())['events']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''): h.update(chunk)
 return h.hexdigest()
rows=[]
for ev in ('N8','N9','N10'):
 root=R/f'drivers_{ev}_v1'
 report=json.loads((root/f'READBACK_GC37X_{ev}_V1.json').read_text())
 assert report['event']==ev and len(report['cycles'])==3
 cycle=dt.datetime.fromisoformat(cfg[ev]['leads']['72h']['t0']).strftime('%Y%m%d%H')
 assert report['cycles'][cycle]['pairs'] in (14,15)
 assert report['cycles'][cycle]['five_fields_31_levels_finite']
 assert report['cycles'][cycle]['shared_byte_equal_pairs']==report['cycles'][cycle]['pairs']
 assert report['cycles'][cycle]['t0_identical']
 assert (root/'SHA256SUMS_CHECK_20261126.log').is_file() or ev=='N9'
 ops=root/f'ops_{ev}_72h_GFS_b2'
 assert (ops/'exitcode').read_text().strip()=='0'
 manifest=json.loads((ops/f'WPS_{cycle}_GFS_REPORT.json').read_text())
 assert len(manifest)==report['cycles'][cycle]['pairs']
 assert all(x['records']==172 and sha(root/x['file'])==x['sha256'] for x in manifest)
 summary=next(I.glob(f'INPUT_GATE_{ev}_72h_{cycle}_v*_SUMMARY.json'))
 gate=json.loads(summary.read_text());assert gate['all_pass'] and gate['global_input_checked']
 source={json.loads(line)['url'].split('/')[-1]:json.loads(line) for line in pathlib.Path(gate['jsonl']).read_text().splitlines()}
 assert (I/f'input_{cycle}_zero.nc').is_file()
 t0=dt.datetime.strptime(cycle,'%Y%m%d%H');tm6=(t0-dt.timedelta(hours=6)).strftime('%Y%m%d%H');tm12=(t0-dt.timedelta(hours=12)).strftime('%Y%m%d%H')
 init={f'gfs.0p25.{tm12}.f006.grib2',f'gfs.0p25.{tm6}.f000.grib2',f'gfs.0p25.{tm6}.f006.grib2',f'gfs.0p25.{cycle}.f000.grib2',f'gfs.0p25b.{tm6}.f000.grib2',f'gfs.0p25b.{cycle}.f000.grib2'}
 d=I/'raw'/cycle
 for p in sorted(d.glob('*.grib2')):
  forecast=bool(re.fullmatch(r'gfs\.0p25\.\d{10}\.f\d{3}\.grib2',p.name) and p.name.startswith(f'gfs.0p25.{cycle}.') and p.name not in init)
  if p.name not in init and not (forecast and ev in ('N8','N10')):raise AssertionError((ev,p))
  s=source[p.name];assert s['sha256'] and p.stat().st_size==s['bytes']
  rows.append({'event':ev,'cycle':cycle,'kind':'initial' if p.name in init else 'forecast','path':str(p),'bytes':s['bytes'],'sha256':s['sha256'],'url':s['url']})
 assert len([x for x in rows if x['event']==ev and x['kind']=='initial'])==6
 assert len([x for x in rows if x['event']==ev and x['kind']=='forecast'])==(14 if ev=='N8' else 13 if ev=='N10' else 0)
assert len(rows)==45
print(json.dumps({'mode':mode,'count':len(rows),'bytes':sum(x['bytes'] for x in rows),'ledger':str(ledger)},ensure_ascii=False),flush=True)
if mode=='--check':sys.exit(0)
for x in rows:assert sha(pathlib.Path(x['path']))==x['sha256'],x['path']
payload={'status':'validated_before_delete','scope':'three 72h paired readbacks passed; same-cycle f006+ forecasts and six verified initialization GRIB only; NetCDF/AI raw retained','files':rows,'deleted_bytes':sum(x['bytes'] for x in rows),'df_before':subprocess.check_output(['df','-B1','/groups/kareem'],text=True)}
with ledger.open('x') as f:json.dump(payload,f,indent=2);f.write('\n')
for x in rows:
 p=pathlib.Path(x['path']);assert p.stat().st_size==x['bytes'];p.unlink();assert not p.exists()
payload['status']='deleted'
payload['df_after']=subprocess.check_output(['df','-B1','/groups/kareem'],text=True)
with ledger.open('w') as f:json.dump(payload,f,indent=2);f.write('\n')
print(json.dumps({'mode':'executed','ledger':str(ledger),'count':len(rows),'deleted_bytes':payload['deleted_bytes'],'df_after':payload['df_after']},ensure_ascii=False),flush=True)
