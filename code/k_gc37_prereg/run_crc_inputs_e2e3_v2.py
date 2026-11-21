#!/usr/bin/env python3
"""Resume CRC E2/E3 gate in a NEW run root; reuse 57 verified historical GRIBs."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numeric_gate_e2e3_crc_v1 as gate
from download_checked_e2e3_v2 import get, digest

OLD = Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37/inputs_2024_E2E3_v1')
NEW = Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37/inputs_2024_E2E3_resume_v2')
BAD_KEY = 'd084001_2024071112_f000'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=str(NEW))
    ap.add_argument('--events', default=str(HERE / 'event_times_gc37.json'))
    args = ap.parse_args()
    root = Path(args.root)
    assert root == NEW and root.is_dir() and root.joinpath('raw').is_symlink()
    assert root.joinpath('raw').resolve() == OLD / 'raw'
    gate.EVENTS = json.loads(Path(args.events).read_text())
    gate.ROOT = root
    objects, cycles = gate.expected()
    assert len(objects) == 93
    old_rows = [json.loads(s) for s in (OLD / 'INPUT_NUMERIC_GATE_E2E3_CRC_V1.jsonl').read_text().splitlines()]
    assert len(old_rows) == 58 and all(r['ok'] for r in old_rows[:57]) and not old_rows[57]['ok']
    assert old_rows[57]['key'] == BAD_KEY
    previous = {r['key']: r for r in old_rows[:57]}
    refs = {gate.str_key(k): {event for event in ('E2', 'E3')
            if any(gate.str_key(k) in keys for name, keys in cycles.items()
                   if name.startswith(event + '_'))} for k in objects}
    gate.precip_times = {k[1] for k in objects if k[0] == 'd084001' and k[2] == 6}
    report = root / 'INPUT_NUMERIC_GATE_E2E3_CRC_V2.jsonl'
    summary_path = root / 'INPUT_NUMERIC_GATE_E2E3_CRC_V2_SUMMARY.json'
    if report.exists() or summary_path.exists():
        raise FileExistsError('immutable v2 output already exists')
    rows = []
    with report.open('x') as out:
        for i, (key, source) in enumerate(objects.items(), 1):
            token = [已隐去]
            target = root / 'raw' / source.rsplit('/', 1)[-1]
            try:
                old = previous.get(token)
                meta = get(source, target, prior_sha=old['sha256'] if old else None,
                           preserve_truncated=(token =[已隐去] BAD_KEY))
                if old:
                    if old['url'] != source or old['bytes'] != meta['bytes']:
                        raise RuntimeError(f'old provenance mismatch: {token}')
                    rec = dict(old)
                    rec['reused_verified'] = True
                else:
                    rec = gate.inspect(key, target, refs[token])
                    rec['reused_verified'] = False
                rec['download_v2'] = meta
            except Exception as exc:
                rec = {'key': token, 'url': source, 'ok': False,
                       'errors': [f'{type(exc).__name__}: {exc}']}
            rows.append(rec)
            out.write(json.dumps(rec) + '\n')
            out.flush()
            print('GATE_FILE', i, len(objects), token,
                  'OK' if rec['ok'] else 'FAIL', rec['errors'][:2], flush=True)
            if not rec['ok']:
                break
    summary = {'expected_files': 93, 'examined_files': len(rows),
               'reused_verified': sum(bool(r.get('reused_verified')) for r in rows),
               'all_pass': len(rows) == 93 and all(r['ok'] for r in rows),
               'dedup_identical': sum(r.get('apcp_dedup', {}).get('dedup_identical', 0) for r in rows),
               'cycle_keys': cycles, 'failures': [r for r in rows if not r['ok']],
               'raw_bytes': sum((root / 'raw' / u.rsplit('/', 1)[-1]).stat().st_size
                                for u in objects.values()
                                if (root / 'raw' / u.rsplit('/', 1)[-1]).exists())}
    summary_path.write_text(json.dumps(summary, indent=2))
    if not summary['all_pass']:
        raise RuntimeError('INPUT_GATE_FAILED: six inputs NOT authorized')
    (root / 'INPUT_NUMERIC_GATE_E2E3_CRC_V2.passed').write_text('PASS\n')
    inputs = []
    for event in ('E2', 'E3'):
        for lead in ('24h', '48h', '72h'):
            cycle = dt.datetime.fromisoformat(gate.EVENTS[event]['leads'][lead]['t0']).strftime('%Y%m%d%H')
            print('BUILD_INPUT', event, lead, cycle, flush=True)
            subprocess.run([sys.executable, str(HERE / 'prepare_gc37_gfs_2024_e2e3_v2.py'),
                            '--cycle', cycle, '--root', str(root)], check=True)
            nc = root / f'input_{cycle}_zero.nc'
            provenance = root / f'input_{cycle}_zero.json'
            assert nc.exists() and provenance.exists()
            prov = json.loads(provenance.read_text())
            assert prov['input_sha256'] == digest(nc)
            inputs.append({'event': event, 'lead': lead, 'cycle': cycle,
                           'netcdf': nc.name, 'sha256': digest(nc),
                           'bytes': nc.stat().st_size, 'provenance': provenance.name})
    (root / 'INPUT_NETCDF_MANIFEST.json').write_text(json.dumps(inputs, indent=2))
    (root / 'INPUTS_READY').write_text('SIX_INPUTS_HASHED\n')
    print('INPUTS_READY', len(inputs), flush=True)


if __name__ == '__main__':
    main()
