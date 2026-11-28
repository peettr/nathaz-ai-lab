#!/usr/bin/env python3
"""Construct preliminary operational GFS cycle manifest, no scoring."""
import csv
from datetime import datetime,timedelta
from pathlib import Path
P=Path(__file__).resolve().parent
rows=[]
for r in csv.DictReader((P.parent/'v2b/input_availability.csv').open()):
 if r['event']=='ISAIAS':continue
 init=datetime.fromisoformat(r['init_utc']);T=init+timedelta(hours=3);gfs=init-timedelta(hours=6)
 rows.append(dict(event=r['event'],aiwp_init_utc=init.isoformat(),assumed_ofcl_public_T_utc=T.isoformat(),gfs_cycle_utc=gfs.isoformat(),gfs_complete_assumed_utc=(gfs+timedelta(hours=4,minutes=15)).isoformat(),gfs_lead_at_aiwp_plus48_h=54,gfs_archive='GDEX d084001 2020 / AWS 2021-24; cycle-specific availability requires verification',provenance=r['gfs_idx_url']))
assert len(rows)==15
with (P/'gfs_cycles_15.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
print('cycles',len(rows),'2020',[(r['event'],r['gfs_cycle_utc']) for r in rows if r['event'] in ('DELTA','ZETA','ETA')])