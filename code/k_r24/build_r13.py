#!/usr/bin/env python3
"""Build immutable-source GFS WPS v5 R13 fields; refuse an existing target."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import numpy as np

FIELDS = ('GHT', 'TT', 'UU', 'VV', 'SPECHUMD')
LEVELS = tuple(x * 100 for x in (1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50))
GROUPS = {'G24': 6, 'G48': 10, 'G72': 14}
SOURCE = Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_akron/v22_final')
TARGET = Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_akron/r13_v22_final')


def records(path):
    with path.open('rb') as f:
        while prefix := f.read(4):
            if len(prefix) != 4: raise ValueError('truncated prefix')
            n, = struct.unpack('>I', prefix)
            if n > 500000000: raise ValueError('absurd record length')
            data, suffix = f.read(n), f.read(4)
            if len(data) != n or suffix != prefix: raise ValueError('bad Fortran record')
            yield prefix + data + suffix


def slabs(path):
    recs = iter(records(path))
    while True:
        try: version = next(recs)
        except StopIteration: return
        if version[4:-4] != struct.pack('>I', 5): raise ValueError('not WPS v5')
        try: rec = (version, next(recs), next(recs), next(recs), next(recs))
        except StopIteration: raise ValueError('incomplete slab') from None
        h = rec[1][4:-4]
        if len(h) != 156: raise ValueError('header size')
        field = h[60:69].decode('ascii').strip()
        level, nx, ny, iproj = struct.unpack('>fiii', h[140:156])
        if len(rec[4]) - 8 != nx*ny*4: raise ValueError('array size')
        yield rec, (field, int(round(level)), nx, ny, iproj)


def arr(rec, nx, ny):
    return np.frombuffer(rec[4][4:-4], dtype='>f4').reshape(ny, nx)


def hash_file(path):
    d = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): d.update(chunk)
    return d.hexdigest()


def transform(src, dst):
    entries = list(slabs(src))
    shape = None
    seen = {k: set() for k in FIELDS}
    heights, humidity = {}, {}
    soil = None
    q2idx = None
    for idx, (recs, (field, lev, nx, ny, proj)) in enumerate(entries):
        if shape is None: shape = (nx, ny, proj, recs[2])
        if shape != (nx, ny, proj, recs[2]): raise ValueError('grid varies')
        if field in FIELDS and lev != 200100:
            if lev in seen[field]: raise ValueError('duplicate level')
            seen[field].add(lev)
            if field == 'GHT': heights[lev] = arr(recs, nx, ny)
            if field == 'SPECHUMD': humidity[lev] = arr(recs, nx, ny)
        if (field, lev) == ('SOILHGT', 200100):
            if soil is not None: raise ValueError('duplicate soil height')
            soil = arr(recs, nx, ny)
        if (field, lev) == ('SPECHUMD', 200100):
            if q2idx is not None: raise ValueError('duplicate Q2')
            q2idx = idx
    if soil is None or q2idx is None: raise ValueError('missing soil/Q2')
    complete = set.intersection(*(seen[f] for f in FIELDS))
    if len(complete) != 31 or any(seen[f] != complete for f in FIELDS):
        raise ValueError('expected 31 complete GFS pressure levels')
    if not set(LEVELS) <= complete: raise ValueError('missing selected level')
    if not np.isfinite(soil).all(): raise ValueError('nonfinite soil')
    new = np.full((ny,nx), np.nan, dtype=np.float32)
    used = np.zeros((ny,nx), dtype=bool)
    counts = {}
    for lev in LEVELS:
        z, q = heights[lev], humidity[lev]
        if not np.isfinite(z).all() or not np.isfinite(q).all(): raise ValueError('nonfinite selected layer')
        eligible = ~used & (z > soil)
        new[eligible] = q[eligible]
        used |= eligible
        counts[str(lev)] = int(eligible.sum())
    if not used.all(): raise ValueError(f'no above-ground level in {int((~used).sum())} cells')
    qold = entries[q2idx][0][4]
    qnew = qold[:4] + new.astype('>f4').tobytes() + qold[-4:]
    if len(qold) != len(qnew): raise ValueError('Q2 size')
    keep = [idx for idx,(rec,(field,lev,*_)) in enumerate(entries)
            if field not in FIELDS or lev == 200100 or lev in LEVELS]
    expected = len(entries) - (31-13)*len(FIELDS)
    if len(keep) != expected or q2idx not in keep: raise ValueError('retained count')
    with dst.open('xb') as f:
        for idx in keep:
            recs = entries[idx][0]
            for j, raw in enumerate(recs): f.write(qnew if idx == q2idx and j == 4 else raw)
        f.flush(); os.fsync(f.fileno())
    # Independent read-back from disk checks every byte of retained slabs and order.
    back = list(slabs(dst))
    if len(back) != len(keep): raise ValueError('readback slab count')
    for pos, idx in enumerate(keep):
        old, oldmeta = entries[idx]
        got, gotmeta = back[pos]
        if oldmeta != gotmeta: raise ValueError(f'metadata at {pos}')
        for j in range(5):
            want = qnew if idx == q2idx and j == 4 else old[j]
            if got[j] != want: raise ValueError(f'raw byte mismatch slab {pos} record {j}')
    if not np.array_equal(arr(back[keep.index(q2idx)][0],nx,ny), new):
        raise ValueError('Q2 array mismatch')
    read_levels = {f: [meta[1] for _, meta in back if meta[0] == f and meta[1] != 200100]
                   for f in FIELDS}
    if any(set(read_levels[f]) != set(LEVELS) or len(read_levels[f]) != 13 for f in FIELDS):
        raise ValueError('readback pressure levels')
    return {'file': str(dst), 'source_sha256': hash_file(src), 'sha256': hash_file(dst),
            'source_slabs':len(entries), 'output_slabs':len(back), 'pressure_levels_pa':list(LEVELS),
            'selected_level_cells':counts, 'q2_changed_cells':int(np.count_nonzero(arr(entries[q2idx][0],nx,ny) != new)),
            'surface_slabs_preserved':sum(1 for idx in keep if entries[idx][1][0] not in FIELDS or entries[idx][1][1] == 200100),
            'nx':nx, 'ny':ny}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, default=SOURCE)
    p.add_argument('--target', type=Path, default=TARGET)
    a = p.parse_args()
    if a.target.exists(): raise SystemExit('REFUSE existing target')
    source_manifest = {}
    for line in (a.source/'SHA256SUMS').read_text().splitlines():
        digest, relative = line.split(maxsplit=1)
        source_manifest[relative.strip('*')] = digest
    inputs = {}
    for group, expected in GROUPS.items():
        files = sorted((a.source/group).glob('GFS25:*'))
        if len(files) != expected or any(not x.is_file() for x in files): raise ValueError(f'input count {group}')
        for src in files:
            key = str(src.relative_to(a.source))
            if key not in source_manifest or hash_file(src) != source_manifest[key]:
                raise ValueError(f'bad source SHA {key}')
        inputs[group] = files
    a.target.mkdir(parents=True)  # exclusive root; never overwrite
    report = {'source':str(a.source), 'target':str(a.target), 'files':[], 'status':'INCOMPLETE'}
    try:
        for group, files in inputs.items():
            (a.target/group.replace('G','R',1)).mkdir()
            for src in files:
                dst = a.target/group.replace('G','R',1)/src.name
                result = transform(src,dst)
                result['file'] = str(dst.relative_to(a.target))
                report['files'].append(result)
                print('DONE', result['file'], result['sha256'], flush=True)
        with (a.target/'SHA256SUMS').open('x') as f:
            for r in report['files']: f.write(r['sha256']+'  '+r['file']+'\n')
        report['status'] = 'PASS'
        with (a.target/'READBACK_R13.json').open('x') as f: json.dump(report,f,indent=2,ensure_ascii=False)
        print('COMPLETE', len(report['files']), 'files',flush=True)
    except Exception as exc:
        (a.target/'INCOMPLETE_ERROR.txt').write_text(repr(exc)+'\n')
        raise

if __name__ == '__main__': main()
