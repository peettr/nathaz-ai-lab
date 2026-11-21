#!/usr/bin/env python3
"""CRC CPU-only E2/E3 GRIB numerical gate, then six GraphCast inputs.

Never starts GraphCast inference. Distinct new root; reports precede any derived inputs.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numeric_gate_e2e3_crc_v1 as gate


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--events', required=True)
    args = ap.parse_args()
    root = Path(args.root)
    assert root.is_absolute() and root.is_dir()
    assert root.resolve().name == 'inputs_2024_E2E3_v1'
    gate.EVENTS = json.loads(Path(args.events).read_text())
    gate.ROOT = root
    objects, cycles = gate.expected()
    assert len(objects) == 93, len(objects)
    gate.precip_times = {k[1] for k in objects if k[0] == 'd084001' and k[2] == 6}
    refs = {gate.str_key(k): {event for event in ('E2', 'E3')
            if any(gate.str_key(k) in keys for name, keys in cycles.items()
                   if name.startswith(event + '_'))} for k in objects}
    report = root / 'INPUT_NUMERIC_GATE_E2E3_CRC_V1.jsonl'
    summary_path = root / 'INPUT_NUMERIC_GATE_E2E3_CRC_V1_SUMMARY.json'
    if report.exists() or summary_path.exists():
        raise FileExistsError('immutable gate output already exists')
    root.joinpath('raw').mkdir(exist_ok=False)
    rows = []
    with report.open('x') as out:
        for i, (key, source) in enumerate(objects.items(), 1):
            name = source.rsplit('/', 1)[-1]
            target = root / 'raw' / name
            try:
                metadata = gate.download(source, target)
                record = gate.inspect(key, target, refs[gate.str_key(key)])
                record['download'] = metadata
            except Exception as exc:
                record = {'key': gate.str_key(key), 'url': source,
                          'ok': False, 'errors': [f'{type(exc).__name__}: {exc}']}
            rows.append(record)
            out.write(json.dumps(record) + '\n')
            out.flush()
            print('GATE_FILE', i, len(objects), record['key'],
                  'OK' if record['ok'] else 'FAIL', record['errors'][:2], flush=True)
            if not record['ok']:
                break
    summary = {'expected_files': 93, 'examined_files': len(rows),
               'all_pass': len(rows) == 93 and all(r['ok'] for r in rows),
               'dedup_identical': sum(r.get('apcp_dedup', {}).get('dedup_identical', 0)
                                      for r in rows),
               'cycle_keys': cycles,
               'failures': [r for r in rows if not r['ok']],
               'grib_bytes': sum((root / 'raw' / u.rsplit('/', 1)[-1]).stat().st_size
                                 for u in objects.values()
                                 if (root / 'raw' / u.rsplit('/', 1)[-1]).exists())}
    summary_path.write_text(json.dumps(summary, indent=2))
    if not summary['all_pass']:
        raise RuntimeError('INPUT_GATE_FAILED: six inputs NOT authorized')
    (root / 'INPUT_NUMERIC_GATE_E2E3_CRC_V1.passed').write_text('PASS\n')
    inputs = []
    for event in ('E2', 'E3'):
        for lead in ('24h', '48h', '72h'):
            cycle = dt.datetime.fromisoformat(gate.EVENTS[event]['leads'][lead]['t0']).strftime('%Y%m%d%H')
            print('BUILD_INPUT', event, lead, cycle, flush=True)
            cmd = [sys.executable, str(HERE / 'prepare_gc37_gfs_2024_e2e3_v2.py'),
                   '--cycle', cycle, '--root', str(root)]
            subprocess.run(cmd, check=True)
            nc = root / f'input_{cycle}_zero.nc'
            provenance = root / f'input_{cycle}_zero.json'
            assert nc.exists() and provenance.exists()
            with provenance.open() as stream:
                prov = json.load(stream)
            assert prov['input_sha256'] == digest(nc)
            inputs.append({'event': event, 'lead': lead, 'cycle': cycle,
                           'netcdf': nc.name, 'sha256': digest(nc),
                           'bytes': nc.stat().st_size, 'provenance': provenance.name})
    (root / 'INPUT_NETCDF_MANIFEST.json').write_text(json.dumps(inputs, indent=2))
    (root / 'INPUTS_READY').write_text('SIX_INPUTS_HASHED\n')
    print('INPUTS_READY', len(inputs), flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        traceback.print_exc()
        raise
