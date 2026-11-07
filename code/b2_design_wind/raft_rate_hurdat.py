#!/usr/bin/env python3
"""Auditable observed-rate proxy; protocol PREREG_v6_RAFT_RATE.md."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import csv, hashlib, json
ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'hurdat2-1851-2025-092326.txt'
lines = SRC.read_text().splitlines()
storms = []
i = 0
while i < len(lines):
    h = [x.strip() for x in lines[i].split(',') if x.strip()]
    assert h[0].startswith('AL') and len(h[0]) == 8 and len(h) == 3, (i, h)
    ident, name, n = h[0], h[1], int(h[2]); i += 1
    records = []
    for _ in range(n):
        f = [x.strip() for x in lines[i].split(',')]; i += 1
        assert len(f) >= 8 and f[3] in ('TD','TS','HU','EX','SD','SS','LO','WV','DB'), (ident, f)
        records.append((datetime.strptime(f[0]+f[1], '%Y%m%d%H%M'), f[3], int(f[6])))
    assert records and len(records) == n and all(records[k][0] <= records[k+1][0] for k in range(n-1))
    storms.append((ident,name,records))
rows=[]
for ident,name,records in storms:
    yr = int(ident[4:]);
    if yr < 1979 or yr > 2018: continue
    tropical = [r for r in records if r[1] in ('TD','TS','HU')]
    qualifying = [r for r in records if r[1] in ('TS','HU') and r[2] >= 35]
    span_hours = (tropical[-1][0]-tropical[0][0]).total_seconds()/3600 if tropical else 0
    rows.append({'id':ident,'name':name,'year':yr,'n_records':len(records),
                 'tropical_span_hours':span_hours,'max_tropical_kt':max((r[2] for r in tropical),default=-999),
                 'has_ts_hu35':bool(qualifying),'main_qualifies':bool(qualifying) and span_hours >= 24,
                 'first_qualifying_utc':qualifying[0][0].isoformat() if qualifying else ''})
assert len(rows)==len({r['id'] for r in rows})
counts=Counter(r['year'] for r in rows if r['main_qualifies'])
loose=Counter(r['year'] for r in rows if r['has_ts_hu35'])
years=[{'year':yr,'all_hurdat_storms':sum(r['year']==yr for r in rows),'ts_hu35':loose[yr], 'ts_hu35_life24h':counts[yr]} for yr in range(1979,2019)]
assert len(years)==40 and sum(x['ts_hu35_life24h'] for x in years)==sum(r['main_qualifies'] for r in rows)
rate=sum(counts.values())/40
assert 0<rate<40
with (ROOT/'hurdat_rate_storm_audit.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
with (ROOT/'hurdat_rate_annual.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=years[0].keys());w.writeheader();w.writerows(years)
summary={'source':'https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt',
         'source_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(), 'period':[1979,2018],
         'n_years':40,'n_all_storms':len(rows),'n_ts_hu35':sum(loose.values()),
         'n_ts_hu35_life24h':sum(counts.values()),'rate_main_per_year':rate,
         'rate_no_life_filter_per_year':sum(loose.values())/40,
         'raft_n_total':40000,'raft_equivalent_years':40000/rate,
         'definition':'AL ID year; TS/HU with >=35 kt at least one record; TD/TS/HU first-to-last span >=24 hours'}
with (ROOT/'hurdat_rate_summary.json').open('x') as f: json.dump(summary,f,indent=2)
print(json.dumps(summary,indent=2))
