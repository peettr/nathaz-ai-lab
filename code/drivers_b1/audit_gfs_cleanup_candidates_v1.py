#!/usr/bin/env python3
"""Read-only GFS WPS checksum audit and disposable-forecast GRIB inventory."""
import hashlib
import json
import pathlib
import re
import sys

root = pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
inputs = root / 'inputs_N1N3N4_v1'
cycles = {'N1': ['2024061418', '2024061318'], 'N3': ['2022070418'], 'N4': ['2022042200', '2022042100']}
rows = []
for event, stamps in cycles.items():
    for stamp in stamps:
        ops = root / f'drivers_{event}_v1' / f'ops_{event}_{"24h" if stamp in ("2024061418", "2022070418", "2022042200") else "48h"}_GFS_b1'
        report = ops / f'WPS_{stamp}_GFS_REPORT.json'
        if not report.exists() or not (ops / 'exitcode').exists():
            rows.append({'event': event, 'cycle': stamp, 'error': 'report_or_exit_absent'})
            continue
        exitcode = (ops / 'exitcode').read_text().strip()
        records = json.loads(report.read_text())
        checked = []
        for entry in records:
            path = root / f'drivers_{event}_v1' / entry['file']
            h = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(4*1024*1024), b''):
                    h.update(block)
            checked.append({'file': str(path), 'sha256_match': h.hexdigest() == entry['sha256'], 'records': entry['records']})
        raw = inputs / 'raw' / stamp
        candidates = []
        for path in sorted(raw.glob('*.grib2')):
            m = re.fullmatch(r'gfs\.0p25b?\.(\d{10})\.f(\d{3})\.grib2', path.name)
            if m and m.group(1) == stamp and int(m.group(2)) >= 6:
                candidates.append({'path': str(path), 'bytes': path.stat().st_size})
        rows.append({'event': event, 'cycle': stamp, 'exitcode': exitcode,
                     'report': str(report), 'wps_count': len(records),
                     'wps_sha_ok': all(x['sha256_match'] and x['records'] == 172 for x in checked),
                     'candidate_files': candidates, 'candidate_bytes': sum(c['bytes'] for c in candidates)})
print(json.dumps({'audit': rows}, ensure_ascii=False, indent=2))
