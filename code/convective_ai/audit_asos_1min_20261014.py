"""Read-only IEM/NCEI ASOS 1-minute cross-check, ±1h from NCEI peak."""
import csv
import datetime as dt
import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
rows = list(csv.DictReader((ROOT / 'events_verified.csv').open(newline='')))
out = ROOT / 'asos_1min_audit_20261014.csv'
fields = ['event_id', 'station', 'ncei_peak_utc', 'ncei_peak_kt', 'one_min_at_peak_kt',
          'one_min_max_kt', 'one_min_max_utc', 'one_min_rows', 'status', 'source_url']
with out.open('x', newline='') as fh:
    writer = csv.DictWriter(fh, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        peak = dt.datetime.strptime(row['peak_utc'], '%Y-%m-%d %H:%MZ')
        start, end = peak - dt.timedelta(hours=1), peak + dt.timedelta(hours=1, minutes=1)
        params = {'station': row['station'], 'tz': 'UTC', 'vars': 'gust_sknt',
                  'sample': '1min', 'what': 'view', 'delim': 'comma'}
        for suffix, t in [('1', start), ('2', end)]:
            for name, value in [('year', t.year), ('month', t.month), ('day', t.day),
                                ('hour', t.hour), ('minute', t.minute)]:
                params[name + suffix] = value
        url = 'https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?' + urllib.parse.urlencode(params)
        record = dict(event_id=row['event_id'], station=row['station'],
                      ncei_peak_utc=row['peak_utc'], ncei_peak_kt=row['peak_gust_kt'],
                      source_url=url)
        try:
            with urllib.request.urlopen(url, timeout=45) as response:
                body = response.read().decode('utf-8-sig')
            observations = list(csv.DictReader(io.StringIO(body)))
            valid = []
            for obs in observations:
                try:
                    valid.append((int(obs['gust_sknt']), obs['valid(UTC)']))
                except (ValueError, KeyError, TypeError):
                    pass
            at_peak = [v for v, t in valid if t == peak.strftime('%Y-%m-%d %H:%M')]
            best = max(valid, default=(None, None))
            record.update(one_min_at_peak_kt=max(at_peak, default=None),
                          one_min_max_kt=best[0], one_min_max_utc=best[1],
                          one_min_rows=len(valid))
            expected = float(row['peak_gust_kt'])
            record['status'] = ('confirmed_peak' if at_peak and max(at_peak) == expected and best[0] == expected
                                else 'peak_missing_or_discrepant')
        except Exception as exc:
            record['status'] = 'fetch_error:' + repr(exc)
            record['one_min_rows'] = 0
        writer.writerow(record)
        fh.flush()
        print(json.dumps(record, ensure_ascii=False), flush=True)
