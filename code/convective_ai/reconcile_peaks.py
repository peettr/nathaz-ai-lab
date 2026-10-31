"""Append-only reconciliation of IEM PK WND physical peak vs METAR valid time."""
import csv,json
from pathlib import Path
p=Path(__file__).parent
rows=[json.loads(s) for s in (p/'observations.jsonl').read_text().splitlines() if s.startswith('{')]
with (p/'event_peak_corrections.csv').open('x',newline='') as f:
    w=csv.writer(f);w.writerow(['event_id','ncei_peak_utc','iem_peak_wind_time_utc','iem_metar_valid_utc','gust_kt','interpretation'])
    for r in rows:
        y=next((x for x in r['iem_top'] if x.get('peak_wind_gust')==r['ncei_kt']),None)
        if y is None:raise RuntimeError('no matching gust '+r['id'])
        w.writerow([r['id'],r['utc'],y['peak_wind_time']+'Z',y['valid']+'Z',r['ncei_kt'],'physical peak = NCEI report time / PK WND; events.csv peak_utc may be METAR valid time'])
print(len(rows),'reconciled')
