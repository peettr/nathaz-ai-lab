#!/usr/bin/env python3
"""Fail-closed OpenFOAM cellProcAddressing -> serial cell permutation."""
import gzip, hashlib, json, re, sys
from pathlib import Path
import numpy as np

grade, case_s, counts_s, output_s, expected_s, nranks_s, dict_sha = sys.argv[1:]
case, output = Path(case_s), Path(output_s)
expected, nranks = int(expected_s), int(nranks_s)
original = json.loads(Path(counts_s).read_text())[grade]
assert len(original) == nranks and sum(original) == expected
actual = []
arrays = []
for rank in range(nranks):
    path = case / f'processor{rank}' / 'constant/polyMesh/cellProcAddressing'
    text = path.read_text()
    if not re.search(r'\bformat\s+ascii\s*;', text[:4096]):
        raise ValueError(f'{path}: not ASCII')
    match = re.search(r'\bclass\s+labelList\s*;', text[:4096])
    if not match:
        raise ValueError(f'{path}: not labelList')
    # Match the list whose count immediately precedes the opening parenthesis.
    lists = list(re.finditer(r'(?m)^\s*(\d+)\s*\n\s*\(', text))
    if len(lists) != 1:
        raise ValueError(f'{path}: ambiguous list header ({len(lists)})')
    m = lists[0]
    count = int(m.group(1))
    tail = text[m.end():]
    end = re.search(r'(?m)^\s*\)\s*;?\s*$', tail)
    if not end:
        raise ValueError(f'{path}: no list close')
    tokens = [已隐去]
    if len(tokens) != count or any(re.fullmatch(r'\d+', token) is None for token in tokens):
        raise ValueError(f'{path}: malformed count or addressing')
    arr = np.asarray(tokens, dtype=np.int64)
    if len(arr) != count:
        raise ValueError(f'{path}: bad array')
    actual.append(count)
    arrays.append(arr)
perm = np.concatenate(arrays)
counts_equal = actual == original
permutation = len(perm) == expected and np.array_equal(np.sort(perm), np.arange(expected, dtype=np.int64))
report = {
    'grade': grade, 'serial_cell_count': expected, 'rank_count': nranks,
    'decomposeParDict_sha256': dict_sha,
    'original_counts': original, 'recreated_counts': actual,
    'counts_equal': counts_equal, 'permutation_0_to_n_minus_1': bool(permutation),
    'mapping': 'serial_index = perm[global_index]; global_index=processor0 local order then processor1 ...',
    'source': 'CRC meshconv_v2 original rank0 logs and original decomposeParDict; regenerated meshgeom input',
}
output.mkdir(parents=True, exist_ok=True)
(output / f'{grade}_partition_counts.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k not in ('original_counts','recreated_counts')}, ensure_ascii=False), flush=True)
if not (counts_equal and permutation):
    raise SystemExit(42)
with gzip.open(output / f'{grade}_perm.npy.gz', 'wb', compresslevel=6) as fp:
    np.save(fp, perm, allow_pickle=False)
