#!/usr/bin/env python3
"""R23.4c-③ GC37 expansion (B tier) event lists. Plan 扩样方案_GC37_20261122.md §1; delegation #6b5f6254.
Main pool: frozen R23.4b events_r3.csv (sha256 c103e67f...f892), SAME rule as k_gc37_prereg/select_events_gc37.py
  (2018-2024; radar_40 True; 'TS' in METAR; obs_kt>=60; 30<=lat<=45; -105<=lon<=-90; sort (kt desc, utc asc, id asc);
  first per date and first per station). Picked[0:4] = E2,E3,R1,R2 (asserted, already used) -> main pool = picked[4:].
Secondary pool: frozen R23.4b events_r4.csv (sha256 8a01f4e2...90e7), same rule WITHOUT radar_40 (column absent;
  radar condition is judged by the observation gate, written in advance). Within r4 first per date and per station;
  then drop entries whose station equals a used event (E1 AKO, E2-E3, R1-R2) or a main-pool station.
Only observation-metadata columns are read (id, station, utc, obs_kt, lat, lon, year, radar_40, metar); no score columns.
Usage: python3 -I select_events_gc37x.py <events_r3.csv> <events_r4.csv> <out.json>"""
import csv, hashlib, json, sys
r3, r4, out = sys.argv[1:4]
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
s3, s4 = sha(r3), sha(r4)
assert s3 == 'c103e67f0cb0f6185c727539732bf0849f03c405fe7975b9332f88ccf617f892', s3
assert s4 == '8a01f4e2b910df3dc05a67eef35fa054c3b2110595bf1e71f758b9e2190e90e7', s4
def eligible(rows, need_radar):
    el = [r for r in rows if 2018 <= int(r['year']) <= 2024 and (not need_radar or r['radar_40'] == 'True')
          and 'TS' in r['metar'] and float(r['obs_kt']) >= 60 and 30 <= float(r['lat']) <= 45 and -105 <= float(r['lon']) <= -90]
    el.sort(key=lambda r: (-float(r['obs_kt']), r['utc'], int(r['id'])))
    dates, st, picked = set(), set(), []
    for r in el:
        d = r['utc'][:10]
        if d in dates or r['station'] in st: continue
        dates.add(d); st.add(r['station']); picked.append(r)
    return el, picked
keys = ['id', 'station', 'utc', 'obs_kt', 'lat', 'lon', 'state', 'year', 'metar']
rows3 = list(csv.DictReader(open(r3))); el3, p3 = eligible(rows3, True)
assert [r['id'] for r in p3[:4]] == ['1181730', '1201334', '1198755', '1194447'], [r['id'] for r in p3[:4]]
main = p3[4:]
used_st = {'AKO'} | {r['station'] for r in p3[:4]}
rows4 = list(csv.DictReader(open(r4))); el4, p4 = eligible(rows4, False)
main_st = {r['station'] for r in main}
dropped = [r for r in p4 if r['station'] in used_st | main_st]
sec = [r for r in p4 if r['station'] not in used_st | main_st]
used_dates = {'2020-06-09'} | {r['utc'][:10] for r in p3}
assert not ({r['utc'][:10] for r in sec} & used_dates), 'secondary date overlaps used/main date'
res = {'source_r3': r3, 'source_r3_sha256': s3, 'source_r4': r4, 'source_r4_sha256': s4,
       'n_r3_eligible': len(el3), 'n_r3_picked': len(p3), 'n_r4_eligible': len(el4), 'n_r4_picked': len(p4),
       'used': {k: p3[i]['id'] for i, k in enumerate(['E2', 'E3', 'R1', 'R2'])},
       'main': [dict(order='N%d' % (i + 1), **{k: r[k] for k in keys}) for i, r in enumerate(main)],
       'secondary': [dict(order='S%d' % (i + 1), **{k: r[k] for k in keys}) for i, r in enumerate(sec)],
       'secondary_dropped_same_station': [{k: r[k] for k in keys[:5]} for r in dropped]}
json.dump(res, open(out, 'w'), indent=1, ensure_ascii=False)
for r in res['main'] + res['secondary']: print(r['order'], r['id'], r['station'], r['utc'], r['obs_kt'], r['lat'], r['lon'])
print('dropped', [(r['station'], r['utc'][:10]) for r in dropped])
