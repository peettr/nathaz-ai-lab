"""Read-only first-round window-edge audit; never edits original results.

The 7 events were previously inspected and cannot count toward a blind r2 test.
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'metrics.jsonl'
DEST = HERE / 'r1_window_edge_audit.csv'
if DEST.exists():
    raise FileExistsError(f'Will not overwrite existing result: {DEST}')
rows = [json.loads(line) for line in SOURCE.read_text().splitlines()]
rows = [r for r in rows if r.get('status') == 'ok']
assert len(rows) == 28 and len({(r['id'], r['lead_h']) for r in rows}) == 28
fields = ['id', 'station', 'lead_h', 'peak_utc', 'init_utc', 'model',
          'observed_gust_ms', 'wide_ms', 'wide_ratio_to_observed',
          'wide_distance_km', 'wide_edge_ge_22_5km', 'narrow_ms',
          'narrow_ratio_to_observed', 'narrow_distance_km', 'wide_hit_ge_25_7',
          'narrow_hit_ge_25_7', 'source']
with DEST.open('x', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in sorted(rows, key=lambda r: (r['id'], r['lead_h'])):
        obs = row['obs_kt'] * .514444
        for key in ('ai', 'hrrr_speed', 'hrrr_gust'):
            wide, narrow = row[key]['wide'], row[key]['narrow']
            writer.writerow(dict(id=row['id'], station=row['station'], lead_h=row['lead_h'],
                peak_utc=row['peak_utc'], init_utc=row['init_utc'], model=key,
                observed_gust_ms=f'{obs:.4f}', wide_ms=f"{wide['value_ms']:.4f}",
                wide_ratio_to_observed=f"{wide['value_ms']/obs:.4f}",
                wide_distance_km=f"{wide['distance_km']:.2f}",
                wide_edge_ge_22_5km=int(wide['distance_km'] >= 22.5),
                narrow_ms=f"{narrow['value_ms']:.4f}" if narrow else '',
                narrow_ratio_to_observed=f"{narrow['value_ms']/obs:.4f}" if narrow else '',
                narrow_distance_km=f"{narrow['distance_km']:.2f}" if narrow else '',
                wide_hit_ge_25_7=int(wide['value_ms'] >= 25.7),
                narrow_hit_ge_25_7=int(narrow['value_ms'] >= 25.7) if narrow else '',
                source='first round metrics.jsonl; NOAA Storm Events/IEM ASOS; AWS HRRR; ERA5/ARCO; StormCast V1'))
from collections import Counter
counts = Counter()
with DEST.open(newline='') as stream:
    for row in csv.DictReader(stream):
        counts[row['model']] += int(row['wide_edge_ge_22_5km'])
print('source_rows', len(rows), 'output_rows', sum(1 for _ in csv.DictReader(DEST.open(newline=''))))
for model in ('ai', 'hrrr_speed', 'hrrr_gust'):
    print(model, 'edge', counts[model], '/', len(rows), f'{counts[model]/len(rows):.3f}')
print(DEST)
