#!/usr/bin/env python3
"""Instantiate frozen design rows into candidate frame/tower geometry.

Output is geometry only, NOT an OpenSees model or validated dataset.
Run on an allocated CRC node. Anchor trees are supplied read-only and are
never copied to the public quick-trial directory.
"""
import argparse
import csv
import hashlib
import json
import math
import random
from pathlib import Path


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def frame(row):
    n, bays = int(row['floor_count']), int(row['bay_count'])
    rng = random.Random(int(row['seed']))
    story_height = rng.uniform(3.2, 4.2)
    bay_width = rng.uniform(5.0, 8.0)
    setback_level = max(2, n // 2) if row['irregularity'] == 'setback' else None
    soft_level = max(2, n // 3) if row['irregularity'] == 'soft_story' else None
    floor_bays = [bays if setback_level is None or level < setback_level
                  else max(1, bays - 1) for level in range(n + 1)]
    nodes, elements = [], []
    node_ids = {}
    for level, count in enumerate(floor_bays):
        for j in range(count + 1):
            ident = f'n{level:02d}_{j:02d}'
            node_ids[(level, j)] = ident
            nodes.append({'id': ident, 'x_m': round(j * bay_width, 8),
                          'y_m': round(level * story_height, 8),
                          'fixed': level == 0, 'floor': level})
    for level in range(1, n + 1):
        for j in range(min(floor_bays[level], floor_bays[level - 1]) + 1):
            elements.append({'id': f'c{level:02d}_{j:02d}', 'kind': 'column',
                             'i': node_ids[(level-1, j)], 'j': node_ids[(level, j)],
                             'soft_scale': 0.55 if level == soft_level else 1.0})
    for level in range(1, n + 1):
        for j in range(floor_bays[level]):
            elements.append({'id': f'b{level:02d}_{j:02d}', 'kind': 'beam',
                             'i': node_ids[(level, j)], 'j': node_ids[(level, j+1)],
                             'soft_scale': 1.0})
    partitions = [[level for level in range(a, min(a+4, n+1))]
                  for a in range(1, n+1, 4)]
    return {'kind': 'candidate_2d_frame_geometry', 'units': 'm',
            'not_for_design': True, 'nodes': nodes, 'elements': elements,
            'floor_bays': floor_bays, 'substructures_floor_groups': partitions,
            'story_height_m': story_height, 'bay_width_m': bay_width,
            'soft_story': soft_level, 'setback_start': setback_level,
            'NOTE': 'Sections, masses, damping and yielding laws are not assigned here.'}


def tower(row, anchor_root):
    root = anchor_root / row['anchor']
    inputs = {name: root / name for name in
              ('nodes.csv', 'elements.csv', 'sections.csv', 'dof_map.csv')}
    for path in inputs.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    with inputs['nodes.csv'].open(newline='') as f:
        nodes = list(csv.DictReader(f))
    with inputs['elements.csv'].open(newline='') as f:
        elements = list(csv.DictReader(f))
    with inputs['sections.csv'].open(newline='') as f:
        sections = list(csv.DictReader(f))
    if not nodes or not elements or not sections:
        raise ValueError('empty anchor CSV: ' + str(root))
    # Until the actual schema and element formulation are qualified, never
    # synthesize fake panel topology. Preserve the anchor's connectivity.
    return {'kind': 'candidate_tower_anchor_inventory', 'not_for_design': True,
            'anchor': row['anchor'], 'proposed_height_scale': float(row['height_scale']),
            'proposed_section_scale': float(row['section_scale']),
            'proposed_segment_count': int(row['segment_count']),
            'anchor_counts': {'nodes': len(nodes), 'elements': len(elements),
                              'sections': len(sections)},
            'anchor_sha256': {name: file_hash(path) for name, path in inputs.items()},
            'status': 'anchor_only; no perturbed tower topology or FE model',
            'NOTE': 'Original anchor is candidate/not_for_design; C partially calibrated.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--anchor-root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if args.out.exists():
        p.error('refusing to overwrite ' + str(args.out))
    with args.manifest.open(newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 300 or len({r['geometry_id'] for r in rows}) != 300:
        raise ValueError('expected 300 unique design rows')
    data = []
    for row in rows:
        g = frame(row) if row['family'] == 'frame' else tower(row, args.anchor_root)
        if g['kind'] == 'candidate_2d_frame_geometry':
            ids = {n['id'] for n in g['nodes']}
            assert all(e['i'] in ids and e['j'] in ids and e['i'] != e['j']
                       for e in g['elements'])
            assert all(len(group) in (1, 2, 3, 4)
                       for group in g['substructures_floor_groups'])
        data.append({'geometry_id': row['geometry_id'], 'split': row['split'],
                     'group_key': row['group_key'], 'geometry': g})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf8') as f:
        json.dump({'manifest_sha256': file_hash(args.manifest), 'rows': data,
                   'status': 'geometry inventory, not solver output'}, f,
                  ensure_ascii=False, separators=(',', ':'))
        f.write('\n')
    print(json.dumps({'rows': len(data), 'path': str(args.out),
                      'sha256': file_hash(args.out),
                      'status': 'geometry inventory only, not a validated FE model'}))


if __name__ == '__main__':
    main()
