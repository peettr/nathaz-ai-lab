"""Correct METAR valid time versus actual PK WND peak without replacing prior draft."""
import csv
from pathlib import Path
p=Path(__file__).parent
corr={r['event_id']:r for r in csv.DictReader((p/'event_peak_corrections.csv').open())}
rows=list(csv.DictReader((p/'events.csv').open()))
for r in rows:
    k=corr[r['event_id']]
    assert float(r['peak_gust_kt'])==float(k['gust_kt'])
    r['peak_utc']=k['iem_peak_wind_time_utc']
    r['metar_report_utc']=k['iem_metar_valid_utc']
with (p/'events_verified.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('verified event rows',len(rows))
