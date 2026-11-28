#!/usr/bin/env python3
"""Serial per-cycle CRC input gate and GFS WPS, with a <20 GB task write cap.

Only files this job created in its new raw directory are removed after their
URL, complete length and SHA256 have been recorded and GFS WPS has passed.
No existing project/result file is removed. Exit on the first failed field.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numeric_gate_r1r2_v1 as gate
from download_checked_e2e3_v2 import get, digest

BASE = Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37')
ROOT = BASE / 'inputs_2024_R1R2_v1'
CAP = 19_000_000_000  # conservative hard gate below requested 20 GB decimal


def size_tree(root):
    roots = [root, BASE / 'drivers_gc37_R1_v1', BASE / 'drivers_gc37_R2_v1']
    return sum(p.stat().st_size for r in roots if r.exists()
               for p in r.rglob('*') if p.is_file() and not p.is_symlink())


def check_size(root, stage, ledger):
    size = size_tree(root)
    ledger['peak_bytes'] = max(ledger['peak_bytes'], size)
    ledger['measurements'].append({'stage': stage, 'bytes': size, 'at': dt.datetime.now(dt.timezone.utc).isoformat()})
    if size >= CAP:
        raise RuntimeError(f'WRITE_CAP: {stage} {size} >= {CAP}')
    return size


def persist(root, ledger):
    p = root / 'DISK_LEDGER.json'
    p.write_text(json.dumps(ledger, indent=2))


def run(command):
    print('RUN', command, flush=True)
    subprocess.run(command, check=True)


def main():
    assert ROOT.is_dir() and (ROOT / 'raw').is_dir()
    assert not (ROOT / 'INPUT_R1R2_SUMMARY.json').exists()
    gate.ROOT = ROOT
    gate.EVENTS = json.loads((HERE / 'event_times_gc37.json').read_text())
    objects, cycles = gate.expected()
    gate.precip_times = {k[1] for k in objects if k[0] == 'd084001' and k[2] == 6}
    refs = {gate.str_key(k): {event for event in ('R1', 'R2')
             if any(gate.str_key(k) in keys for name, keys in cycles.items()
                    if name.startswith(event + '_'))} for k in objects}
    ledger = {'cap_bytes': CAP, 'peak_bytes': 0, 'measurements': [], 'cycles': []}
    all_rows = []
    manifest = []
    raw = ROOT / 'raw'
    # Do not overlap task-cycle GRIB names; after one cycle, raw must be empty.
    for event in ('R1', 'R2'):
        for lead in ('24h', '48h', '72h'):
            t0 = dt.datetime.fromisoformat(gate.EVENTS[event]['leads'][lead]['t0'])
            cycle = t0.strftime('%Y%m%d%H')
            cycle_id = f'{event}_{lead}_{cycle}'
            assert not list(raw.iterdir()), ('raw_not_empty', cycle_id)
            keys = set(cycles[f'{event}_{lead}'])
            selected = [(k, u) for k, u in objects.items() if gate.str_key(k) in keys]
            report = ROOT / f'INPUT_GATE_{cycle_id}.jsonl'
            assert not report.exists()
            rows = []
            with report.open('x') as stream:
                for i, (key, url) in enumerate(selected, 1):
                    target = raw / url.rsplit('/', 1)[-1]
                    try:
                        # Max source GRIB from prior campaign was 555 MB. Reserve two
                        # retries and post-download NetCDF/WPS headroom under CAP.
                        if check_size(ROOT, f'{cycle_id}:pre_download_{i}', ledger) > 16_000_000_000:
                            raise RuntimeError('WRITE_CAP_RESERVE: stop before next GRIB')
                        meta = get(url, target)
                        rec = gate.inspect(key, target, refs[gate.str_key(key)])
                        rec['download'] = meta
                    except Exception as exc:
                        rec = {'key': gate.str_key(key), 'url': url, 'ok': False,
                               'errors': [f'{type(exc).__name__}: {exc}']}
                    rows.append(rec)
                    stream.write(json.dumps(rec) + '\n'); stream.flush()
                    check_size(ROOT, f'{cycle_id}:file_{i}', ledger)
                    persist(ROOT, ledger)
                    print('GATE_FILE', cycle_id, i, len(selected), rec['key'],
                          'OK' if rec['ok'] else 'FAIL', rec.get('errors', []), flush=True)
                    if not rec['ok']:
                        raise RuntimeError(f'INPUT_GATE_FAILED: {cycle_id}: {rec}')
            assert len(rows) == len(selected) and all(r['ok'] for r in rows)
            all_rows.extend(rows)
            (ROOT / f'INPUT_GATE_{cycle_id}.passed').write_text('PASS\n')
            run([sys.executable, str(HERE / 'prepare_gc37_gfs_2024_r1r2_v1.py'),
                 '--cycle', cycle, '--root', str(ROOT)])
            nc = ROOT / f'input_{cycle}_zero.nc'
            prov = ROOT / f'input_{cycle}_zero.json'
            assert nc.exists() and prov.exists()
            sha = digest(nc)
            assert json.loads(prov.read_text())['input_sha256'] == sha
            manifest.append({'event': event, 'lead': lead, 'cycle': cycle,
                             'netcdf': nc.name, 'sha256': sha, 'bytes': nc.stat().st_size,
                             'provenance': prov.name})
            check_size(ROOT, f'{cycle_id}:netcdf', ledger); persist(ROOT, ledger)
            run([sys.executable, str(HERE / 'build_gc37_wps_crc_cpu_r1r2_v1.py'),
                 '--cycle', cycle, '--arm', 'GFS'])
            report_wps = BASE / f'drivers_gc37_{event}_v1' / f'ops_cpu_{event}_v1' / f'WPS_{cycle}_GFS_REPORT.json'
            outputs = json.loads(report_wps.read_text())
            assert len(outputs) == 1 + int(gate.EVENTS[event]['leads'][lead]['length_h']) // 6
            for entry in outputs:
                p = BASE / f'drivers_gc37_{event}_v1' / entry['file']
                assert p.is_file() and digest(p) == entry['sha256'], p
            check_size(ROOT, f'{cycle_id}:gfs_wps', ledger)
            # Explicitly authorized only for newly downloaded, reproducible raw GRIB;
            # each source's SHA256/URL/size is in the immutable per-cycle JSONL.
            for rec in rows:
                p = raw / rec['url'].rsplit('/', 1)[-1]
                assert p.is_file() and p.stat().st_size == rec['download']['bytes']
                assert digest(p) == rec['sha256'] == rec['download']['sha256']
                p.unlink()
            assert not list(raw.iterdir())
            ledger['cycles'].append({'cycle': cycle, 'event': event, 'lead': lead,
                                     'grib_files_verified': len(rows), 'gfs_wps_files': len(outputs),
                                     'netcdf_sha256': sha, 'raw_deleted_after_verified_gfs': True})
            check_size(ROOT, f'{cycle_id}:raw_cleaned', ledger); persist(ROOT, ledger)
            print('CYCLE_READY', cycle_id, ledger['peak_bytes'], flush=True)
    assert len(manifest) == 6 and len({x['cycle'] for x in manifest}) == 6
    assert len(objects) == len(all_rows) == 90
    summary = {'expected_files_per_cycle': {k: len(v) for k, v in cycles.items()},
               'unique_source_files': len(objects),
               'examined_files_including_cycle_reuse': len(all_rows),
               'all_pass': all(r['ok'] for r in all_rows),
               'failures': [r for r in all_rows if not r['ok']],
               'dedup_identical': sum(r.get('apcp_dedup', {}).get('dedup_identical', 0) for r in all_rows),
               'peak_bytes_input_and_driver_roots': ledger['peak_bytes'],
               'disk_ledger': str(ROOT / 'DISK_LEDGER.json'),
               'raw_retention': 'per-cycle source URL, length and SHA256 retained; newly downloaded GRIB removed after GFS WPS'}
    assert summary['all_pass'] and summary['peak_bytes_input_and_driver_roots'] < CAP
    (ROOT / 'INPUT_R1R2_SUMMARY.json').write_text(json.dumps(summary, indent=2))
    (ROOT / 'INPUT_NETCDF_MANIFEST.json').write_text(json.dumps(manifest, indent=2))
    (ROOT / 'INPUTS_READY').write_text('SIX_INPUTS_HASHED\n')
    print('INPUTS_READY', len(manifest), flush=True)


if __name__ == '__main__':
    main()
