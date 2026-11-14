#!/usr/bin/env python3
"""Assemble the approved read-only C38.2 S1 handoff from frozen JSON inputs."""
import hashlib
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
S1 = ROOT / '06_Logs/caseA_S1/s1_results.json'
OLD = ROOT / '06_Logs/caseA_r9_2m_tacc_v2/samples_caseA_r9_2m.json'
PREVIOUS = ROOT / '04_Handoffs/C38.2_CaseA_2m_pointvalues_20261107.md'
OUT = ROOT / '04_Handoffs/C38.2_CaseA_2m_pointvalues_S1_20261111.md'
FULL_HASH = OUT.with_suffix('.sha256')
assert not OUT.exists() and not FULL_HASH.exists(), 'Refuse to overwrite existing results'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
s = json.loads(S1.read_text())
o = json.loads(OLD.read_text())
assert s['grids']['dx2']['ground_label_m'] == 1.0 and o['UH'] == 4.491
assert len(s['grids']['dx2']['groups']) == 3
mapping = [('4 m plane (S1 key z8)', 'z8', 'z4_actual'),
           ('40 m plane (S1 key z80)', 'z80', 'z40_actual'),
           ('centre vertical profile', 'vertical', 'vertical_actual')]
lines = [
 '# AIJ Case A round 9, 2 m: S1 per-point values for C38.2 (11-11)',
 '',
 'This is a new point-value handoff, not a replacement for the 11-07 handoff. '
 'All 186 rows are copied from the frozen S1 JSON and paired by group and point ID with the '
 'previous `plus_xyz` point values. The old source and old handoff remain unchanged. '
 'S1 keys `z8` and `z80` denote the 4 m and 40 m observation planes here, '
 'not 8 m and 80 m sampling surfaces.',
 '',
 '## Source files and provenance',
 '',
 '| File (relative to 24_Urban_Wind_LBM) | SHA256 |',
 '|---|---|',
 f'| `{S1.relative_to(ROOT)}` | `{sha(S1)}` |',
 f'| `{OLD.relative_to(ROOT)}` | `{sha(OLD)}` |',
 f'| `{PREVIOUS.relative_to(ROOT)}` | `{sha(PREVIOUS)}` |',
 '',
 'S1 field-input SHA256 values (fluid/u/v/w/k) are recorded in '
 '`s1_results.json` under `grids.dx2.source_fields_sha256`. '
 'The old point source is the 186-point file referenced by the 11-07 handoff.',
 '',
 '## Coordinates, components and sampling',
 '',
 'Official coordinates are metres in the solver frame: x downstream (+x, wind direction 270°), '
 'y lateral, z above the nominal STL ground; the building centre is (352, 352) m and b=32 m. '
 'The official mapping is x=352+32(x/b), y=352+32(y/b), z=32(z/b). '
 'The VTK grid has origin (0, 0, -20) m, spacing 2 m, and shape (x,y,z)=(544,352,192). '
 'u/v/w, where available in the old point source only, are signed time-mean x/y/z velocity '
 'components in m/s; positive w points upwards. Neither S1 JSON nor this table provides new '
 'u/v/w components: speed is |<u,v,w>|/U_H and k is resolved turbulent kinetic energy /U_H², '
 'with U_H=4.491 m/s. The table does not infer components from speed.',
 '',
 'S1 height is above the measured effective ground, whose VTK label is 1.0 m; '
 'the first open-ground fluid centre is label 2.0 m (1.0 m AGL). '
 'For official height h, S1 target VTK label is 1.0+h m (clamped to the first '
 'fluid centre if needed). The selected horizontal shift is (+2,+2) m from solid-mask '
 'IoU, not chosen using velocity metrics. Old `plus_xyz` uses (+2,+2,+2) m '
 'on the nominal VTK-label coordinates; therefore old 4 m samples have label 6 m, '
 'whereas the S1 target label is 5 m. S1 excludes any point with a '
 'positive-weight solid interpolation corner from metrics; all dx2 rows below '
 'are unclamped and unmixed according to the source flags. '
 'The point table retains every row regardless of its metric eligibility.',
 '',
 'Time: one time-averaged field, no time-series splice. Last 22,000 of 32,000 solver steps, '
 'stride 40, 550 samples, approximately 647 s physical time; '
 'the old and S1 values sample the same time-mean field, not independent runs.',
 '',
 '## Per-point values',
 '',
 'All speeds are dimensionless |<u,v,w>|/U_H; all k values are resolved k/U_H². '
 'Δ = S1 − old `plus_xyz`. Obs = wind-tunnel observation. '
 'Official x/y/z are wind-tunnel mapped physical coordinates; S1/old sample z are VTK-label metres; '
 'the S1 actual AGL height is relative to the effective-ground label 1.0 m. '
 'Decimals displayed to 9 places; summary statistics use full precision.',
 '',
 '| Group | ID | Official (x,y,z) m | Obs speed | S1 speed | Old speed | Δspeed | Obs k | S1 k | Old k | Δk | S1 label z m | Old sample z m | Clamped | Solid corners |',
 '|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|',
]
all_ds, all_dk = [], []
stats = []
for title, sk, ok in mapping:
    grp = s['grids']['dx2']['groups'][sk]
    fresh, prior = grp['rows'], o['groups'][ok]
    assert len(fresh) == len(prior) and len(fresh) == grp['total']
    ds, dk = [], []
    for x, y in zip(fresh, prior):
        assert x['id'] == y['id'] and x['coord_m'] == y['official_xyz_m']
        assert x['obs_speed'] == y['obs_speed'] and x['obs_k'] == y['obs_k']
        assert x['clamped'] is False and not x['solid_corners']
        prev = y['plus_xyz']
        assert prev['sample_xyz_m'][:2] == [x['coord_m'][0]+2, x['coord_m'][1]+2]
        d_speed = x['speed'] - prev['speed_UH']
        d_k = x['k'] - prev['k_UH2']
        ds.append(d_speed); dk.append(d_k)
        co = ','.join(f'{v:g}' for v in x['coord_m'])
        f = lambda v: f'{v:.9f}'
        lines.append('| ' + ' | '.join((title, str(x['id']), co,
            f(x['obs_speed']), f(x['speed']), f(prev['speed_UH']), f(d_speed),
            f(x['obs_k']), f(x['k']), f(prev['k_UH2']), f(d_k),
            f(x['label_m']), f(prev['sample_xyz_m'][2]), 'no', '0')) + ' |')
    stats.append((title, len(ds), max(map(abs, ds)), mean(ds), mean(map(abs, ds)),
                  max(map(abs, dk)), mean(dk), mean(map(abs, dk))))
    all_ds.extend(ds); all_dk.extend(dk)
assert len(all_ds) == len(all_dk) == 186
lines.extend(['', '## Pointwise change summary', '',
 'Maximum difference means max |S1−old|; mean difference is signed mean(S1−old); '
 'mean absolute difference is mean |S1−old|. These are differences in '
 'dimensionless speed or k, not changes in a metric such as FAC2.', '',
 '| Group | Points | Max |Δspeed| | Mean Δspeed | Mean |Δspeed| | Max |Δk| | Mean Δk | Mean |Δk| |',
 '|---|---:|---:|---:|---:|---:|---:|---:|---:|'])
for row in stats + [('All points', 186, max(map(abs, all_ds)), mean(all_ds),
                       mean(map(abs, all_ds)), max(map(abs, all_dk)),
                       mean(all_dk), mean(map(abs, all_dk)))]:
    title, n, *values = row
    lines.append('| ' + ' | '.join([title, str(n)] + [f'{v:.9f}' for v in values]) + ' |')
lines.extend(['', '## Integrity of this table', '',
 'SHA256 of all preceding UTF-8 bytes in this Markdown file (including the '
 'newline before this section) cannot be a full-file self-hash. '
 'The full-file SHA256 is stored in the adjacent `.sha256` checksum file. '
 'The next line contains the SHA256 of this document up to but not including '
 'that line, with its final newline; this precise scope avoids a self-reference paradox.', ''])
prefix = ('\n'.join(lines) + '\n').encode('utf-8')
body_digest = hashlib.sha256(prefix).hexdigest()
OUT.write_bytes(prefix + f'Pre-checksum content SHA256: `{body_digest}`\n'.encode())
full_digest = sha(OUT)
FULL_HASH.write_text(f'{full_digest}  {OUT.name}\n', encoding='utf-8')
print('file', OUT, 'sha256', full_digest, 'prefix_sha256', body_digest)
print('stats', stats)
print('overall', len(all_ds), max(map(abs, all_ds)), mean(all_ds), mean(map(abs, all_ds)),
      max(map(abs, all_dk)), mean(all_dk), mean(map(abs, all_dk)))
