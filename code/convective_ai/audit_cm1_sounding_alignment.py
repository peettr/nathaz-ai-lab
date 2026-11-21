"""Audit temporal alignment of archived StormCast soundings against CM1 E5 rule.
Read-only inputs; writes new supplement files, never changes the original comparisons.
"""
import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'cm1_alignment_raob_audit.csv'
assert not OUT.exists(), f'Refusing overwrite: {OUT}'

def utc(s):
    return dt.datetime.fromisoformat(s.strip().replace(' ', 'T').replace('Z', '+00:00'))

events = {r['event_id']: r for r in csv.DictReader((ROOT / 'events_verified.csv').open(newline=''))}
models = {r['event_id']: r for r in map(json.loads, (ROOT / 'soundings_raw.jsonl').open())}
assert len(events) == len(models) == 7 and events.keys() == models.keys()
fields = ['event_id','asos_station','peak_utc','raob_station','raob_utc',
          'raob_minus_peak_h','raob_peak_gap_h','raob_peak_gap_gt3h',
          'raob_relation_to_preconvective_time','legacy_init_utc',
          'cm1_anchor_35dbz_utc','cm1_preconvective_hrrr_analysis_utc',
          'cm1_clean_land_column_lat','cm1_clean_land_column_lon','cm1_status']
with OUT.open('x', newline='') as fp:
    writer = csv.DictWriter(fp, fieldnames=fields); writer.writeheader()
    for eid, e in events.items():
        m = models[eid]
        peak = utc(e['peak_utc']); raob = utc(m['raob_utc'])
        delta = round((raob-peak).total_seconds()/3600, 3)
        writer.writerow(dict(event_id=eid, asos_station=e['station'], peak_utc=e['peak_utc'],
            raob_station=m['raob_station'], raob_utc=m['raob_utc'],
            raob_minus_peak_h=delta, raob_peak_gap_h=abs(delta),
            raob_peak_gap_gt3h=str(abs(delta)>3).lower(),
            raob_relation_to_preconvective_time='unknown: radar anchor not archived',
            legacy_init_utc=m['init_utc'],cm1_status='not evaluated: radar anchor, observed and HRRR reflectivity, land mask missing'))
print('wrote', OUT, 'rows', len(events))
