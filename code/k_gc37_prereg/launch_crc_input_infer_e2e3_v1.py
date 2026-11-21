#!/usr/bin/env python3
"""One-shot Colab worker: restore verified CRC inputs, infer six cycles, archive each cycle."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

R = Path('/content/r234c_gc37_E2E3')
SOURCE = 'gdrive:colab_cache/r234c_e2e3_inputs_20261115_v1'
ARCHIVE = 'gdrive:colab_cache/r234c_e2e3_forecasts_20261115_v1'

def emit(*args):
    msg = f'{dt.datetime.now(dt.timezone.utc).isoformat()} ' + ' '.join(map(str, args))
    print(msg, flush=True)

def run(label, args):
    emit('START', label)
    p = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True)
    emit('END', label, p.returncode, p.stdout[-2500:])
    if p.returncode:
        raise RuntimeError((label, p.returncode, p.stdout[-2500:]))

try:
    R.mkdir(exist_ok=True)
    run('deps', [sys.executable, '-m', 'pip', 'install', '-q', 'pygrib', 'netcdf4', 'dask',
                 'dm-haiku', 'chex', 'jraph', 'rtree', 'trimesh', 'dm-tree',
                 'dinosaur-dycore', 'boto3', 'xarray', 'xarray-tensorstore'])
    run('clone', ['git', 'clone', '--depth', '1', 'https://github.com/NOAA-EMC/graphcast.git',
                  '/content/r234c_graphcast_source'])
    run('restore', ['rclone', 'copy', SOURCE, str(R), '--transfers', '2', '--checkers', '2',
                    '--tpslimit', '5', '--retries', '3'])
    summary = json.loads((R / 'INPUT_NUMERIC_GATE_E2E3_CRC_V2_SUMMARY.json').read_text())
    assert summary['all_pass'] and summary['expected_files'] == summary['examined_files'] == 93 and not summary['failures']
    assert (R / 'INPUT_NUMERIC_GATE_E2E3_CRC_V2.passed').read_text().strip() == 'PASS'
    manifest = json.loads((R / 'INPUT_NETCDF_MANIFEST.json').read_text())
    assert len(manifest) == 6 and len({m['cycle'] for m in manifest}) == 6
    for item in manifest:
        p = R / item['netcdf']
        assert p.stat().st_size == item['bytes'], item
        with p.open('rb') as f:
            assert hashlib.file_digest(f, 'sha256').hexdigest() == item['sha256'], item
        emit('INPUT_HASH_OK', item['cycle'])
    run('weights', [sys.executable, '/content/stage_gc37_weights_e2e3.py'])
    events = json.loads(Path('/content/event_times_gc37.json').read_text())
    for event in ('E2', 'E3'):
        for lead in ('24h', '48h', '72h'):
            t0 = dt.datetime.fromisoformat(events[event]['leads'][lead]['t0'])
            end = dt.datetime.fromisoformat(events[event]['end'])
            steps = int((end - t0).total_seconds() / 21600)
            cycle = t0.strftime('%Y%m%d%H')
            folder = R / f'forecast_{cycle}_{steps}step'
            assert not folder.exists(), folder
            run('infer_'+cycle, [sys.executable, '/content/run_gc37_raw_e2e3.py',
                                  '--cycle', cycle, '--event', event, '--steps', str(steps),
                                  '--root', str(R), '--bbox', '/content/domain_bbox_gc37.json'])
            files = sorted(folder.glob('step_*.npz'))
            assert len(files) == steps, (cycle, len(files), steps)
            records = []
            for p in files:
                with p.open('rb') as f:
                    sha = hashlib.file_digest(f, 'sha256').hexdigest()
                records.append({'file': p.name, 'bytes': p.stat().st_size, 'sha256': sha})
            (folder / 'RAW_MANIFEST.json').write_text(json.dumps(records, indent=2))
            emit('RAW_READY', event, cycle, len(files))
            run('archive_'+cycle, ['rclone', 'copy', str(folder), ARCHIVE + '/' + cycle,
                                   '--transfers', '2', '--checkers', '2', '--tpslimit', '5',
                                   '--retries', '3'])
            run('archive_check_'+cycle, ['rclone', 'check', str(folder), ARCHIVE + '/' + cycle,
                                         '--checksum', '--one-way'])
            emit('ARCHIVED', event, cycle)
    (R / 'infer_crc_inputs.done').write_text('SUCCESS\n')
    emit('SUCCESS_ALL')
except BaseException as exc:
    (R / 'infer_crc_inputs.failed').write_text(repr(exc) + '\n')
    emit('FAILED', repr(exc))
    raise
