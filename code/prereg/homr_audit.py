#!/usr/bin/env python3
"""Metadata-only HOMR audit; no weather/forecast values are fetched.
Run on Colab CPU or as pure HTTP queries. Output is new and exclusive.
"""
import csv, json, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / 'v2c' / 'station_audit_170.csv'
POOL = HERE.parents[1] / 'v2b' / 'hourly_pool_150km.csv'
BASE = 'https://www.ncei.noaa.gov/access/homr/services/station/search'

def load():
    pool = {(r['event'], r['station']): r for r in csv.DictReader(POOL.open()) if r['hourly_75pct'] == 'True'}
    return [(r, pool[(r['event'], r['station'])]) for r in csv.DictReader(SOURCE.open())]

def query(icao):
    url = BASE + '?' + urllib.parse.urlencode(dict(qid='ICAO:' + icao, date='all', definitions='false', phrData='false'))
    try:
        with urllib.request.urlopen(url, timeout=35) as resp:
            obj = json.load(resp)
        matches = [s for s in obj.get('stationCollection', {}).get('stations', [])
                   if any(x.get('idType') == 'ICAO' and x.get('id') == icao for x in s.get('identifiers', []))]
        return url, matches, ''
    except Exception as exc:
        return url, [], repr(exc)

def main():
    src = load()
    icaos = sorted({'K' + r['station'] if len(r['station']) == 3 else r['station'] for r, _ in src})
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(query, i): i for i in icaos}
        lookup = {futures[f]: f.result() for f in as_completed(futures)}
    output = []
    for r, p in src:
        icao = 'K' + r['station'] if len(r['station']) == 3 else r['station']
        url, stations, error = lookup[icao]
        moment = datetime.fromisoformat(p['landfall_utc']).replace(tzinfo=None)
        applicable = []
        for st in stations:
            for platform in st.get('platforms', []):
                span = platform.get('date', {})
                start, end = span.get('beginDate', ''), span.get('endDate', '')
                if (not start or start == 'Unknown' or datetime.fromisoformat(start) <= moment) and (end in ('Present', 'Unknown', '') or datetime.fromisoformat(end) >= moment):
                    applicable.append((st['ncdcStnId'], platform['platform'], start, end))
        match = next(((ident, start, end) for ident, platform, start, end in applicable if platform == 'ASOS'), None)
        # HOMR platform history does not expose numeric wind-sensor height in the returned station object.
        # A 2025 inventory is an explicit proxy, never marked as historically verified height.
        height = r['inventory_height_m']
        commissioned = r['legacy_commission'] and r['legacy_commission'] <= moment.date().isoformat()
        admitted = bool(match and commissioned and height and 7.8 <= float(height) <= 12)
        parallel = admitted and 8 <= float(height) <= 12
        output.append(dict(event=r['event'], landfall_utc=p['landfall_utc'], station=r['station'], icao=icao,
            ncdc_stn_id=match[0] if match else '', homr_url=url,
            homr_platforms=';'.join(sorted(set(x[1] for x in applicable))),
            homr_asos_begin=match[1] if match else '', homr_asos_end=match[2] if match else '',
            homr_status='request_error' if error else 'event_date_asos' if match else 'no_event_date_asos',
            homr_error=error, inventory_url=r['inventory_url'], inventory_height_ft=r['inventory_height_ft'],
            inventory_height_m=height, inventory_commission=r['legacy_commission'],
            height_provenance='2025_inventory_proxy_unverified_at_event' if height else 'missing',
            historically_verified_height='no', primary_eligible='yes_unverified_height' if admitted else 'no',
            parallel_eligible='yes_unverified_height' if parallel else 'no'))
    path = HERE / 'homr_audit.csv'
    with path.open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=output[0].keys()); writer.writeheader(); writer.writerows(output)
    print(json.dumps(dict(rows=len(output), requests=len(lookup), errors=sum(bool(x[2]) for x in lookup.values()),
                          primary=sum(x['primary_eligible'].startswith('yes') for x in output),
                          parallel=sum(x['parallel_eligible'].startswith('yes') for x in output)), ensure_ascii=False))
if __name__ == '__main__': main()
