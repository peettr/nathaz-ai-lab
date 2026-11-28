#!/usr/bin/env python3
"""Read-only GDEX 2022/2024 object inventory; HTTP Range is NOT numerical QC."""
import concurrent.futures as cf
import datetime as dt
import json
import pathlib
import urllib.request
import urllib.error

HERE = pathlib.Path(__file__).resolve().parent
EVENTS = pathlib.Path('./23_AI_Weather/06_Logs/k_gc37x_prereg/event_times_bbox_gc37x.json')
BASE = 'https://osdf-director.osg-htc.org/ncar/gdex/'


def url(year, dataset, t, f):
    stem = 'gfs.0p25b' if dataset == 'd084003' else 'gfs.0p25'
    return f'{BASE}{dataset}/{year}/{t:%Y%m%d}/{stem}.{t:%Y%m%d%H}.f{f:03d}.grib2'


def probe(item):
    u = item['url']
    try:
        req = urllib.request.Request(u, headers={'Range': 'bytes=0-3', 'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=35) as r:
            hdr = r.read(4)
            return {**item, 'http': r.status, 'prefix': hdr.decode('ascii', 'replace'),
                    'content_range': r.headers.get('Content-Range'),
                    'metadata_access': bool(r.status == 206 and hdr == b'GRIB')}
    except Exception as e:
        return {**item, 'http': getattr(e, 'code', None), 'error': str(e), 'metadata_access': False}


def main():
    config = json.loads(EVENTS.read_text())['events']
    rows = []
    for ev in ('N1', 'N3', 'N4'):
        e = config[ev]
        end = dt.datetime.fromisoformat(e['end'])
        for lead, rec in e['leads'].items():
            t0 = dt.datetime.fromisoformat(rec['t0'])
            for t in (t0 - dt.timedelta(hours=6), t0):
                for dataset in ('d084001', 'd084003'):
                    rows.append({'event': ev, 'lead': lead, 'role': 'analysis', 'dataset': dataset,
                                 'cycle': t.strftime('%Y%m%d%H'), 'forecast_h': 0,
                                 'url': url(t.year, dataset, t, 0)})
                p = t - dt.timedelta(hours=6)
                rows.append({'event': ev, 'lead': lead, 'role': 'apcp_0_6', 'dataset': 'd084001',
                             'cycle': p.strftime('%Y%m%d%H'), 'forecast_h': 6,
                             'url': url(p.year, 'd084001', p, 6)})
            for h in range(6, int((end-t0).total_seconds()/3600)+1, 6):
                rows.append({'event': ev, 'lead': lead, 'role': 'boundary', 'dataset': 'd084001',
                             'cycle': t0.strftime('%Y%m%d%H'), 'forecast_h': h,
                             'url': url(t0.year, 'd084001', t0, h)})
    # Deduplicate network objects while preserving event/lead uses.
    unique = {r['url']:r for r in rows}
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        response = dict(zip(unique, ex.map(probe, unique.values())))
    result = {'method': 'bounded HTTP Range first 4 bytes; never substitute for full GRIB decode',
              'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'records': len(rows), 'unique_urls': len(unique),
              'events': {ev: {lead: [{**r, 'range_probe': response[r['url']]} for r in rows if r['event']==ev and r['lead']==lead]
                              for lead in config[ev]['leads']} for ev in ('N1','N3','N4')}}
    out = HERE / 'INPUT_PRECHECK_N1N3N4_RANGE_v1.json'
    if out.exists(): raise FileExistsError(out)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('SAVED', out, 'records',len(rows),'unique',len(unique),'accessible',sum(x['metadata_access'] for x in response.values()),flush=True)
    for ev in ('N1','N3','N4'):
        for lead in config[ev]['leads']:
            subset=result['events'][ev][lead]
            fail=[f"{r['role']}:{r['cycle']}:f{r['forecast_h']:03d}:HTTP={r['range_probe']['http']}" for r in subset if not r['range_probe']['metadata_access']]
            print(ev,lead,'objects',len(subset),'range_fail',fail,flush=True)


if __name__ == '__main__':main()
