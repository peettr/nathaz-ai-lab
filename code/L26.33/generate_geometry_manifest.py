#!/usr/bin/env python3
"""Generate a deterministic GEOMETRY DESIGN MANIFEST; not solver data.

Run on CRC after group-rule approval. The script does not copy private anchor files,
solve structures, or claim that candidate geometries have passed mesh/FE checks.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import random

FIELDS = ["geometry_id", "family", "split", "group_key", "seed", "anchor",
          "floor_count", "bay_count", "irregularity", "segment_count",
          "height_scale", "section_scale", "holdout_subgroup", "anchor_source_sha256", "status"]


def make_rows():
    rows = []
    # Each group is assigned to exactly one split. Group keys include a partition
    # code for the parameter stratum, not an individual geometry identifier.
    def frame_pool(split):
        if split == 'geometry_holdout':
            raise ValueError('holdout uses the three frozen subgroups below')
        all_groups = [(f,b,t) for f in range(5,21) for b in range(1,6)
                      for t in ('regular','soft_story')]
        # Disjoint *whole* groups while all three splits retain the same ranges.
        scored = [(g, hashlib.sha256(repr(g).encode()).digest()[0] % 10)
                  for g in all_groups]
        return [g for g, v in scored if
                (split == 'train' and v < 8) or
                (split == 'validation' and v == 8) or
                (split == 'iid_reference' and v == 9)]
    bands = [('train',1,160), ('validation',161,180),
             ('iid_reference',181,200), ('geometry_holdout',201,240)]
    for split, lo, hi in bands:
        pool = frame_pool(split) if split != 'geometry_holdout' else None
        for index in range(lo, hi + 1):
            if split == 'geometry_holdout':
                if index <= 215:
                    subgroup = 'floor_extrapolation'
                    choices = [(f, b, t) for f in range(22, 31) for b in range(1, 6)
                               for t in ('regular', 'soft_story')]
                    offset = index - 201
                elif index <= 230:
                    subgroup = 'setback_extrapolation'
                    choices = [(f, b, 'setback') for f in range(5, 21) for b in range(1, 6)]
                    offset = index - 216
                else:
                    subgroup = 'combined_extrapolation'
                    choices = [(f, b, 'setback') for f in range(22, 31) for b in range(1, 6)]
                    offset = index - 231
                floor, bay, irregularity = choices[offset % len(choices)]
            else:
                assert pool, split
                floor, bay, irregularity = pool[(index-lo) % len(pool)]
                subgroup = ''
            group = f"F:{floor:02d}:{bay}:{irregularity}"
            rows.append(dict(geometry_id=f"F{index:03d}", family="frame", split=split,
                             group_key=group, seed=2633000 + index, anchor="",
                             floor_count=floor, bay_count=bay, irregularity=irregularity,
                             segment_count=(floor + 3) // 4, height_scale="",
                             section_scale="", status="design_only_unvalidated",
                             holdout_subgroup=subgroup, anchor_source_sha256=""))
    tbands = [('train',1,36,('A_q1_official','B'),(4,5),'regular'),
              ('validation',37,44,('A_q1_official','B'),(6,),'regular'),
              ('iid_reference',45,50,('A_q1_official','B'),(6,),'panel_softening'),
              ('geometry_holdout',51,60,('C',),(4,5,6),'regular')]
    for split, lo, hi, anchors, segs, irregularity in tbands:
        for index in range(lo, hi + 1):
            rng = random.Random(2634000 + index)
            anchor = anchors[(index - lo) % len(anchors)]
            segment_count = segs[(index-lo) // len(anchors) % len(segs)]
            group = f"T:{anchor}:{segment_count}:{irregularity}"
            rows.append(dict(geometry_id=f"T{index:03d}", family="tower", split=split,
                             group_key=group, seed=2634000 + index, anchor=anchor,
                             floor_count="", bay_count="", irregularity=irregularity,
                             segment_count=segment_count,
                             height_scale=f"{rng.uniform(0.9, 1.1):.6f}",
                             section_scale=f"{rng.uniform(0.85, 1.15):.6f}",
                             status="design_only_unvalidated", holdout_subgroup="tower_C",
                             anchor_source_sha256=""))
    return rows


def validate(rows):
    assert len(rows) == 300
    assert len({r['geometry_id'] for r in rows}) == 300
    groups = {}
    for row in rows:
        g, s = row['group_key'], row['split']
        assert g not in groups or groups[g] == s, (g, groups[g], s)
        groups[g] = s
        if row['family'] == 'frame' and s == 'geometry_holdout':
            n, kind = int(row['floor_count']), row['irregularity']
            subgroup = row['holdout_subgroup']
            assert (subgroup == 'floor_extrapolation' and 22 <= n <= 30 and kind in ('regular','soft_story')) or (subgroup == 'setback_extrapolation' and 5 <= n <= 20 and kind == 'setback') or (subgroup == 'combined_extrapolation' and 22 <= n <= 30 and kind == 'setback')
        if row['family'] == 'tower' and s == 'geometry_holdout':
            assert row['anchor'] == 'C'
    for family, want in [('frame', (160,20,20,40)), ('tower', (36,8,6,10))]:
        counts = tuple(sum(r['family'] == family and r['split'] == s for r in rows)
                       for s in ('train','validation','iid_reference','geometry_holdout'))
        assert counts == want, (family, counts)
    for subgroup, want in [('floor_extrapolation', 15), ('setback_extrapolation', 15),
                           ('combined_extrapolation', 10)]:
        assert sum(r['holdout_subgroup'] == subgroup for r in rows) == want


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True, type=Path, help='NEW CSV path on CRC')
    args = p.parse_args()
    if args.out.exists():
        p.error('refusing overwrite: ' + str(args.out))
    rows = make_rows()
    validate(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({'rows': len(rows), 'sha256': hashlib.sha256(args.out.read_bytes()).hexdigest(),
                      'path': str(args.out), 'status': 'DESIGN ONLY; NOT FE VALIDATED'}, ensure_ascii=False))

if __name__ == '__main__':
    main()
