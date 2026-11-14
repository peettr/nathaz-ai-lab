"""Validate frozen R4 two-VM successful keys and merge without altering sources."""
import collections
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
SOURCES = [ROOT / 's2_vm1_1108/final_1108_2025.jsonl', ROOT / 's2_vm2_1108/final/incremental_110_200.jsonl']
OUT = ROOT / 'r4_score_final_1109/merged_200.jsonl'
assert not OUT.exists(), f'will not overwrite {OUT}'
all_lines = []
manifest = {}
for source, (start, end) in zip(SOURCES, [(0, 110), (110, 200)]):
    lines = source.read_bytes().splitlines()
    by_unit = collections.defaultdict(set)
    for line in lines:
        r = json.loads(line)
        assert r['status'] == 'ok' and start <= r['unit_index'] < end
        key = (r['kind'], r.get('seed'))
        assert key not in by_unit[r['unit_index']], (source, r['unit_index'], key)
        by_unit[r['unit_index']].add(key)
    expected = {('baseline', None)} | {('member', seed) for seed in range(101, 111)}
    assert set(by_unit) == set(range(start, end)), (start, end, set(range(start, end)) - set(by_unit))
    assert all(keys == expected for keys in by_unit.values())
    manifest[source.name] = {'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'rows': len(lines), 'units': len(by_unit), 'range': [start, end]}
    all_lines.extend(lines)
assert len(all_lines) == 2200
OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open('xb') as f:
    for line in all_lines:
        f.write(line + b'\n')
manifest['merged'] = {'path': str(OUT), 'sha256': hashlib.sha256(OUT.read_bytes()).hexdigest(), 'rows': len(all_lines), 'units': 200, 'rerun_required': 0}
manifest_path = OUT.parent / 'merge_manifest.json'
with manifest_path.open('x') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(json.dumps(manifest, ensure_ascii=False))
