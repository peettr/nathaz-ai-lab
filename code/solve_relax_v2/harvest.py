#!/usr/bin/env python3
"""Append-only bounded G1 telemetry harvest from node scratch to shared root.
The scratch case is disposable; no predecessor research result is changed.
"""
import argparse
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

p = argparse.ArgumentParser()
p.add_argument('case', type=Path)
p.add_argument('destination', type=Path)
p.add_argument('grade')
p.add_argument('--once', action='store_true')
a = p.parse_args()
case = a.case
out = a.destination
out.mkdir(parents=True, exist_ok=True)
# Each invocation gets a unique immutable artifact; monitor remembers emitted states.
MAX_GRADE = 250_000_000
MAX_ALL = 14_900_000_000
ROOT = Path('/groups/kareem/[用户]')

def all_bytes():
    roots = sorted(ROOT.glob('L26_21_DAFOAM_*'))
    cmd = ['du', '-sB1', *map(str, roots)]
    r = subprocess.run(cmd, text=True, capture_output=True, check=True)
    return sum(int(line.split()[0]) for line in r.stdout.splitlines())

def used():
    r = subprocess.run(['du', '-sB1', str(out)], text=True, capture_output=True, check=True)
    return int(r.stdout.split()[0])

def emit(src, label, compress=True, field=False):
    if not src.is_file():
        return 'absent'
    # The bound uses uncompressed size, conservatively, before the write.
    size = src.stat().st_size
    reserve = size + 1_000_000
    if used() + reserve > MAX_GRADE or all_bytes() + reserve > MAX_ALL:
        return 'cap_skip_field' if field else 'cap_skip_table'
    dst = out / (label + ('.gz' if compress else ''))
    if dst.exists():
        return 'exists'
    with dst.open('xb') as raw:
        if compress:
            with gzip.GzipFile(fileobj=raw, mode='wb', compresslevel=1) as z, src.open('rb') as f:
                shutil.copyfileobj(f, z)
        else:
            with src.open('rb') as f:
                shutil.copyfileobj(f, raw)
        raw.flush()
        os.fsync(raw.fileno())
    return f'bytes={dst.stat().st_size}'

def collect(seq):
    items = [
        (case/'g1_progress.jsonl', 'progress', False),
        (case/'g1_gate.json', 'primal_gate', False),
        (case/'g1_adjoint_gate.json', 'adjoint_gate', False),
        (case/'g1_fd.json', 'gradient_fd', False),
        (case/'empty_reference.json', 'empty_reference', False),
        (case/'sample_cells.json', 'sample_cells', False),
        (case/'g1_rank0.log', 'rank0', False),
        (case/'g1_cp_trace.csv', 'cp_trace', False),
        (case/'g1_gate_error.txt', 'gate_error', False),
    ]
    for name, sub in [('roofMean', 'surfaceFieldValue.dat'), ('forces', 'forces.dat'), ('forceCoeffs', 'forceCoeffs.dat')]:
        folder = case/'postProcessing'/name
        if folder.exists():
            items.extend((file, f'{name}_{i}', False) for i, file in enumerate(sorted(folder.glob('*/'+sub))))
    for folder in sorted((case/'postProcessing').glob('*')) if (case/'postProcessing').exists() else []:
        if 'yPlus' in folder.name:
            items.extend((f, f'yplus_{i}', False) for i, f in enumerate(sorted(folder.glob('*/*.dat'))))
    items.extend((f, f'rank_{i:02d}_tail', False)
                 for i, f in enumerate(sorted(case.glob('rank_*.tail.log'))))
    result = {}
    for src, name, field in items:
        result[name] = emit(src, f'{a.grade}_{seq:04d}_{name}', field=field)
    # Immutable receipt, on scratch so monitoring never overwrites a result.
    print(json.dumps({'seq': seq, 'at': time.time(), 'files': result, 'shared_bytes': all_bytes(), 'grade_bytes': used()}), flush=True)

seen = 0
last = None
while True:
    progress = case/'g1_progress.jsonl'
    if progress.exists():
        lines = progress.read_text(errors='replace').splitlines()
        if len(lines) > seen:
            for line in lines[seen:]:
                try: phase = json.loads(line).get('phase')
                except json.JSONDecodeError: phase = 'malformed'
                # Each phase boundary is a durable, independently bounded snapshot.
                seen += 1
                collect(seen)
                last = phase
    if a.once:
        collect(seen + 1)
        break
    time.sleep(30)
