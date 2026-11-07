"""Materialize frozen geometry-nested seed orders on the eligible v5 training pool.

The v5 seed orders include six excluded cases; remove those, then choose the
closest group-boundary prefix at each N. No held-out case is inspected.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'group_split_v5.json'
OUTPUT = ROOT / 'v6_nested_subsets.json'


def group(case):
    return case.rsplit('_d', 1)[0]


def build(source):
    allowed = source['train_cases']
    allowed_set = set(allowed)
    assert len(allowed) == len(allowed_set) == 371
    assert len(source['val_cases']) == 34 and len(source['test_cases']) == 100
    assert not (allowed_set & set(source['val_cases']))
    assert not (allowed_set & set(source['test_cases']))
    assert not (set(source['val_cases']) & set(source['test_cases']))
    assert len({group(c) for c in allowed}) == 160
    assert not ({group(c) for c in allowed} & {group(c) for c in source['val_cases'] + source['test_cases']})
    output = {'source': SOURCE.name,
              'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              'method': 'v5 seed group order, excluded cases removed; closest complete-group prefix per target (ties smaller); fixed validation and test',
              'val_cases': source['val_cases'], 'test_cases': source['test_cases'],
              'seeds': {}}
    for seed in ('17', '42', '73'):
        original = source['seeds'][seed]['all']
        ordered = [c for c in original if c in allowed_set]
        assert len(ordered) == len(set(ordered)) == 371 and set(ordered) == allowed_set
        group_order = list(dict.fromkeys(group(c) for c in ordered))
        groups = {g: [c for c in ordered if group(c) == g] for g in group_order}
        assert len(groups) == 160
        sequence = [c for g in group_order for c in groups[g]]
        assert sequence == ordered, 'v5 seed order must keep group members contiguous'
        boundaries = [sum(len(groups[g]) for g in group_order[:i]) for i in range(1, len(group_order) + 1)]
        rows = {}
        for target in (50, 100, 200):
            size = min(boundaries, key=lambda x: (abs(x-target), x))
            cases = sequence[:size]
            rows[str(target)] = {'target_cases': target, 'actual_cases': size,
                                  'actual_groups': len({group(c) for c in cases}), 'cases': cases}
        rows['all'] = {'target_cases': 371, 'actual_cases': 371, 'actual_groups': 160, 'cases': sequence}
        assert all(set(rows[a]['cases']) <= set(rows[b]['cases']) for a,b in [('50','100'),('100','200'),('200','all')])
        output['seeds'][seed] = rows
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = build(json.loads(SOURCE.read_text()))
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.check:
        assert OUTPUT.read_text() == text
    else:
        assert not OUTPUT.exists(), 'never overwrite an existing manifest'
        OUTPUT.write_text(text)
    for seed, rows in result['seeds'].items():
        print(seed, {k: (v['actual_cases'],v['actual_groups']) for k,v in rows.items()})
