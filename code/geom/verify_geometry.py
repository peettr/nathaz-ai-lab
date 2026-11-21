#!/usr/bin/env python3
"""Verify re-created mesh cell indexing against frozen meshconv directions."""
import gzip, hashlib, io, json, re, sys
from pathlib import Path
import numpy as np

grade, case_s, reference_s, out_s, expected_s = sys.argv[1:]
case, reference, out = Path(case_s), Path(reference_s), Path(out_s)
out.mkdir(parents=True, exist_ok=True)
expected = int(expected_s)
ref = json.load(gzip.open(reference, 'rt'))
assert ref['n'] == expected and ref['grade'] == grade

def read_field(path, kind):
    text = path.read_text()
    if not re.search(r'\bformat\s+ascii\s*;', text[:4096]):
        raise ValueError(f'{path}: not ASCII')
    marker = 'vector' if kind == 'vector' else 'scalar'
    m = re.search(r'\binternalField\s+nonuniform\s+List<' + marker + r'>\s+(\d+)\s*\(', text)
    if not m or int(m.group(1)) != expected:
        raise ValueError(f'{path}: count mismatch')
    tail = text[m.end():]
    end = re.search(r'(?m)^\s*\)\s*;\s*$', tail)
    if not end: raise ValueError(f'{path}: missing closing list')
    body = tail[:end.start()]
    if kind == 'vector':
        rows = re.findall(r'(?m)^\s*\(\s*([-+\deE.]+)\s+([-+\deE.]+)\s+([-+\deE.]+)\s*\)\s*$', body)
        data = np.asarray(rows, dtype=np.float64)
    else:
        rows = re.findall(r'(?m)^\s*([-+\deE.]+)\s*$', body)
        data = np.asarray(rows, dtype=np.float64)
    if len(data) != expected or not np.isfinite(data).all():
        raise ValueError(f'{path}: parsed {len(data)} != {expected} or non-finite')
    return data

C = read_field(case/'0/C', 'vector')
V = read_field(case/'0/V', 'scalar')
if np.any(V <= 0): raise ValueError('nonpositive volume')
x,y,z = C.T
vectors = {
    'v2_building_1H': ((x>=-16)&(x<=16)&(y>=-16)&(y<=16)&(z>=0)&(z<=16)).astype(np.float64),
    'v3_wake_5H': ((x>=8)&(x<=48)&(y>=-12)&(y<=12)&(z>=0)&(z<=12)).astype(np.float64),
}
center_sha = hashlib.sha256((case/'0/C').read_bytes()).hexdigest()
vector_checks = {key: {'sha256':hashlib.sha256(arr.tobytes()).hexdigest(), 'count':int(np.count_nonzero(arr)), 'match':hashlib.sha256(arr.tobytes()).hexdigest()==ref['directions'][key]['sha256']} for key,arr in vectors.items()}
center_match = center_sha == ref['centres_sha256']
match = center_match or all(x['match'] for x in vector_checks.values())
for name, arr in (('centres',C),('volumes',V)):
    with gzip.open(out/f'{grade}_{name}.npy.gz','wb',compresslevel=6) as fp:
        np.save(fp,arr,allow_pickle=False)
result={'grade':grade,'n':expected,'centre_file_sha256':center_sha,'reference_centre_sha256':ref['centres_sha256'],'centres_exact_match':center_match,'directions':vector_checks,'index_verified':match,'volume_min':float(V.min()),'volume_max':float(V.max()),'source':'CRC L26.21 meshconv v2 case inputs; regenerated mesh'}
(out/f'{grade}_verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(result,ensure_ascii=False))
if not match: sys.exit(42)
