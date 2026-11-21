#!/usr/bin/env python3
"""Infer six frozen cycles only from CRC-built, hash-verified 2024 inputs."""
import datetime as dt
import hashlib
import json
import pathlib
import subprocess

R = pathlib.Path('/content/r234c_gc37_E2E3')
EVENTS = json.loads(pathlib.Path('/content/event_times_gc37.json').read_text())
LOG = R / 'infer_crc_inputs.log'

def emit(*args):
    with LOG.open('a') as f:
        print(dt.datetime.now().astimezone().isoformat(), *args, file=f, flush=True)

def stage(label, command):
    emit('STAGE_START', label)
    with (R / (label + '.log')).open('x') as f:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT)
    emit('STAGE_END', label, result.returncode)
    if result.returncode:
        raise RuntimeError((label, result.returncode))

try:
    summary = json.loads((R / 'INPUT_NUMERIC_GATE_E2E3_CRC_V2_SUMMARY.json').read_text())
    assert summary['all_pass'] and summary['expected_files'] == summary['examined_files'] == 93 and not summary['failures']
    assert (R / 'INPUT_NUMERIC_GATE_E2E3_CRC_V2.passed').read_text().strip() == 'PASS'
    manifest = json.loads((R / 'INPUT_NETCDF_MANIFEST.json').read_text())
    assert len(manifest) == 6 and len({e['cycle'] for e in manifest}) == 6
    for item in manifest:
        p = R / item['netcdf']
        assert p.stat().st_size == item['bytes'], item
        with p.open('rb') as f:
            assert hashlib.file_digest(f, 'sha256').hexdigest() == item['sha256'], item
        emit('INPUT_HASH_OK', item['cycle'], item['sha256'])
    stage('weights', ['python3', '/content/stage_gc37_weights_e2e3.py'])
    for event in ('E2', 'E3'):
        for lead in ('24h', '48h', '72h'):
            t0 = dt.datetime.fromisoformat(EVENTS[event]['leads'][lead]['t0'])
            end = dt.datetime.fromisoformat(EVENTS[event]['end'])
            steps = int((end-t0).total_seconds()/21600)
            cycle = t0.strftime('%Y%m%d%H')
            assert (R / f'input_{cycle}_zero.nc').exists()
            stage('infer_'+cycle, ['python3', '/content/run_gc37_raw_e2e3.py', '--cycle', cycle, '--event', event, '--steps', str(steps), '--root', str(R), '--bbox', '/content/domain_bbox_gc37.json'])
            folder = R / f'forecast_{cycle}_{steps}step'
            files = sorted(folder.glob('step_*.npz'))
            assert len(files) == steps, (cycle, len(files), steps)
            records = []
            for p in files:
                with p.open('rb') as f:
                    sha = hashlib.file_digest(f, 'sha256').hexdigest()
                records.append({'file': p.name, 'bytes': p.stat().st_size, 'sha256': sha})
            (R / f'RAW_MANIFEST_{cycle}.json').write_text(json.dumps(records, indent=2))
            emit('RAW_READY', event, cycle, len(files))
    (R / 'infer_crc_inputs.done').write_text('SUCCESS\n')
    emit('SUCCESS_ALL')
except BaseException as exc:
    emit('FAILED', repr(exc))
    (R / 'infer_crc_inputs.failed').write_text(repr(exc) + '\n')
    raise
