#!/usr/bin/env python3
"""R23.4c-② GC37 event selection (prereg v2, ruling eb769a94 item 7).
Input: frozen R23.4b list events_r3.csv (sha256 c103e67f...f892). Uses only observation metadata columns:
id, station, utc, obs_kt, lat, lon, year, radar_40, metar. Does NOT read any model/score columns.
Rule: year 2018-2024; radar_40 True; 'TS' in METAR; obs_kt >= 60; 30<=lat<=45; -105<=lon<=-90;
sort by (obs_kt desc, utc asc, id asc); keep first per date AND first per station; first 2 -> E2,E3, next 2 -> R1,R2.
E1 = Akron CO 2020-06-09 (KAKO) fixed.
Usage: python3 -I select_events_gc37.py <events_r3.csv> <out.json>
"""
import csv, hashlib, json, sys
src, out = sys.argv[1], sys.argv[2]
sha = hashlib.sha256(open(src, 'rb').read()).hexdigest()
assert sha == 'c103e67f0cb0f6185c727539732bf0849f03c405fe7975b9332f88ccf617f892', sha
rows = list(csv.DictReader(open(src)))
el = [r for r in rows
      if 2018 <= int(r['year']) <= 2024 and r['radar_40'] == 'True' and 'TS' in r['metar']
      and float(r['obs_kt']) >= 60 and 30 <= float(r['lat']) <= 45 and -105 <= float(r['lon']) <= -90]
el.sort(key=lambda r: (-float(r['obs_kt']), r['utc'], int(r['id'])))
dates, stations, picked = set(), set(), []
for r in el:
    d = r['utc'][:10]
    if d in dates or r['station'] in stations:
        continue
    dates.add(d); stations.add(r['station']); picked.append(r)
keys = ['id', 'station', 'utc', 'obs_kt', 'lat', 'lon', 'state', 'year', 'metar']
res = {'source': src, 'source_sha256': sha, 'n_rows': len(rows), 'n_eligible': len(el),
       'E1': {'id': 'AKRON_K', 'station': 'AKO', 'utc': '2020-06-09T06:10:00', 'obs_kt': round(37.04/0.514444, 1),
              'lat': 40.17563, 'lon': -103.22203, 'note': 'fixed; Childs 2021 Table 2 (card GZYPXN4S PDF p.16)'},
       'E2': {k: picked[0][k] for k in keys}, 'E3': {k: picked[1][k] for k in keys},
       'R1': {k: picked[2][k] for k in keys}, 'R2': {k: picked[3][k] for k in keys},
       'next_reserves': [{k: r[k] for k in keys[:5]} for r in picked[4:8]]}
json.dump(res, open(out, 'w'), indent=1, ensure_ascii=False)
for k in ['E2', 'E3', 'R1', 'R2']:
    r = res[k]; print(k, r['id'], r['station'], r['utc'], r['obs_kt'], r['lat'], r['lon'])
