#!/usr/bin/env python3
"""Delete only approved re-downloadable cycle forecasts after GFS readback.

The input NetCDF, t0 and prior analyses are never removed. Fail closed on any
provenance/hash mismatch. Single invocation only; no automatic retries.
"""
import hashlib
import json
import pathlib
import re
import subprocess

base = pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
root = base / 'inputs_N1N3N4_v1'
cycles = [('N1','24h','2024061418','v4'),('N1','48h','2024061318','v4'),
          ('N3','24h','2022070418','v3'),('N4','24h','2022042200','v4'),
          ('N4','48h','2022042100','v4')]
ledger = root / 'FORECAST_GRIB_CLEANUP_20261124_v1.json'
if ledger.exists(): raise FileExistsError(ledger)
rows=[]
for event, lead, stamp, ver in cycles:
    report = base / f'drivers_{event}_v1' / f'ops_{event}_{lead}_GFS_b1' / f'WPS_{stamp}_GFS_REPORT.json'
    exitfile = report.parent / 'exitcode'
    assert exitfile.read_text().strip() == '0', exitfile
    records = json.loads(report.read_text())
    assert len(records) == (6 if lead == '24h' else 10)
    assert all(r['records'] == 172 and r['arm'] == 'GFS' and r['cycle'] == stamp for r in records)
    for rec in records:
        dest=base/f'drivers_{event}_v1'/rec['file']
        h=hashlib.sha256()
        with dest.open('rb') as f:
            for block in iter(lambda:f.read(4*1024*1024),b''): h.update(block)
        assert h.hexdigest() == rec['sha256'], dest
    gatepath=root/f'INPUT_GATE_{event}_{lead}_{stamp}_{ver}.jsonl'
    provenance={x['key']:x for x in (json.loads(s) for s in gatepath.read_text().splitlines())}
    assert json.loads((root/f'INPUT_GATE_{event}_{lead}_{stamp}_{ver}_SUMMARY.json').read_text())['all_pass']
    raw=root/'raw'/stamp
    assert raw.is_dir() and (root/f'input_{stamp}_zero.nc').is_file()
    candidates=[]
    for file in sorted(raw.iterdir()):
        m=re.fullmatch(r'gfs\.0p25(b?)\.(\d{10})\.f(\d{3})\.grib2',file.name)
        if not m or m.group(2)!=stamp or int(m.group(3))<6: continue
        key=f'd08400{3 if m.group(1) else 1}_{stamp}_f{m.group(3)}'
        entry=provenance[key]
        assert entry['sha256'] and entry['bytes'] == file.stat().st_size, file
        h=hashlib.sha256()
        with file.open('rb') as f:
            for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
        assert h.hexdigest()==entry['sha256'],file
        candidates.append({'path':str(file),'bytes':entry['bytes'],'sha256':entry['sha256'],'url':entry['url']})
    assert len(candidates)==(5 if lead=='24h' else 9), (stamp,len(candidates))
    rows.append({'event':event,'cycle':stamp,'gate':str(gatepath),'wps_report':str(report),'files':candidates,'bytes':sum(x['bytes'] for x in candidates)})
# Freeze the complete checked deletion list *before* touching any file.
ledger.write_text(json.dumps({'policy':'delete only current cycle forecast f006+ after GFS WPS readback; retain t0 and prior analyses','rows':rows},indent=2)+'\n')
for row in rows:
    for entry in row['files']:
        pathlib.Path(entry['path']).unlink()
print(json.dumps({'ledger':str(ledger),'deleted_files':sum(len(x['files']) for x in rows),
                  'deleted_bytes':sum(x['bytes'] for x in rows),
                  'df_after':subprocess.check_output(['df','-B1','/groups/kareem'],text=True).strip()},ensure_ascii=False))
