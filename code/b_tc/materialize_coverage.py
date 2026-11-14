#!/usr/bin/env python3
"""Materialize verified coverage without overwriting first-pass events.csv."""
import csv
from pathlib import Path
p=Path(__file__).resolve().parent
rows=list(csv.DictReader((p/'events.csv').open())); cov=list(csv.DictReader((p/'aiwp_object_coverage.csv').open()))
for r in rows:
 for short,model in [('PANG','PANG_v100_GFS'),('FOUR','FOUR_v200_GFS'),('GRAP','GRAP_v100_GFS')]:
  x={int(v['lead_target_h']):v['object_present'] for v in cov if v['event']==r['name'] and v['model']==model}
  r[short+'_24_48_72']='|'.join(x[h] for h in (24,48,72))
 r['model_coverage_note']='Verified actual S3 object per nearest prior 00/12 UTC cycle for each nominal lead; see aiwp_object_coverage.csv; does not verify internal variables'
with (p/'events_verified.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
print('verified rows',len(rows))
