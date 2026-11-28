#!/usr/bin/env python3
"""Anchor/windows/init times and d01 crop box for GC37 expansion candidates (N1-N13, S1-S8).
Logic copied verbatim from frozen k_gc37_prereg/event_times_gc37.py (PK WND anchor -> nearest 10 min; exist [a-3h,a+3h];
onset [a-6h,a+3h]; t0 = floor6(a) - 24/48/72 h; end = first 6-h boundary >= a+3h) and domain_bbox_gc37.py
(Lambert 748x600 dx 4 km, CEN=TRUELAT=round(lat), STAND_LON=round(lon), crop = floor/ceil of 8 edge points +/-3 deg).
Self-check: reproduces frozen event_times_gc37.json / domain_bbox_gc37.json for E2,E3,R1,R2 before processing candidates.
Usage: python3 -I event_times_bbox_gc37x.py events_gc37x.json <k_gc37_prereg dir> out.json"""
import json, math, re, sys
from datetime import datetime, timedelta
from pathlib import Path
def pk(e):
    t = datetime.fromisoformat(e['utc'])
    m = re.search(r'PK WND \d{5,6}/(\d{2})?(\d{2})', e.get('metar', ''))
    if not m: return t, 'report_time'
    hh = int(m.group(1)) if m.group(1) else t.hour
    c = t.replace(hour=hh, minute=int(m.group(2)), second=0)
    if c > t + timedelta(hours=1): c -= timedelta(days=1)
    return c, 'PK_WND'
def times(e):
    t, src = pk(e)
    a = datetime(t.year, t.month, t.day, t.hour) + timedelta(minutes=10 * round((t.minute + t.second / 60) / 10))
    f6 = a.replace(minute=0) - timedelta(hours=a.hour % 6)
    end = a + timedelta(hours=3)
    if end.minute or end.hour % 6: end = end.replace(minute=0) + timedelta(hours=(6 - end.hour % 6) % 6 or (6 if end.minute else 0))
    rec = {'station': e['station'], 't_obs': t.isoformat(), 't_obs_src': src, 'anchor': a.isoformat(),
           'exist_win': [(a - timedelta(hours=3)).isoformat(), (a + timedelta(hours=3)).isoformat()],
           'onset_win': [(a - timedelta(hours=6)).isoformat(), (a + timedelta(hours=3)).isoformat()],
           'end': end.isoformat(), 'leads': {}}
    for L in (24, 48, 72):
        t0 = f6 - timedelta(hours=L)
        rec['leads'][f'{L}h'] = {'t0': t0.isoformat(), 'length_h': (end - t0).total_seconds() / 3600}
    return rec
def pts(clat, clon):
    R = 6370.0; p1 = math.radians(clat); n = math.sin(p1)
    F = math.cos(p1) * math.tan(math.pi / 4 + p1 / 2) ** n / n
    r0 = R * F / math.tan(math.pi / 4 + p1 / 2) ** n
    def inv(x, y):
        rho = math.copysign(math.hypot(x, r0 - y), n); th = math.atan2(x, r0 - y)
        return math.degrees(2 * math.atan((R * F / rho) ** (1 / n)) - math.pi / 2), clon + math.degrees(th / n)
    hx, hy = 747 * 4 / 2, 599 * 4 / 2
    return [inv(x, y) for x in (-hx, 0, hx) for y in (-hy, 0, hy) if (x, y) != (0, 0)]
def bbox(e):
    clat, clon = round(float(e['lat'])), round(float(e['lon']))
    P = pts(clat, clon); la = [p[0] for p in P]; lo = [p[1] for p in P]
    box = [math.floor(min(la)) - 3, math.ceil(max(la)) + 3, math.floor(min(lo)) - 3, math.ceil(max(lo)) + 3]
    return {'cen_lat': clat, 'cen_lon': clon, 'd01_lat': [min(la), max(la)], 'd01_lon': [min(lo), max(lo)],
            'crop_lat': box[:2], 'crop_lon_west_neg': box[2:]}
ev = json.load(open(sys.argv[1])); pre = Path(sys.argv[2])
old_sel = json.load(open(pre / 'events_selected_gc37.json')); old_t = json.load(open(pre / 'event_times_gc37.json')); old_b = json.load(open(pre / 'domain_bbox_gc37.json'))
for k in ['E2', 'E3', 'R1', 'R2']:
    assert times(old_sel[k]) == old_t[k], k
    assert bbox(old_sel[k]) == old_b[k], k
out = {'selftest_E2E3R1R2': 'reproduced frozen event_times_gc37.json and domain_bbox_gc37.json', 'events': {}}
for e in ev['main'] + ev['secondary']:
    rec = times(e); rec.update(id=e['id'], order=e['order'], obs_kt=e['obs_kt'], lat=float(e['lat']), lon=float(e['lon']), domain=bbox(e))
    out['events'][e['order']] = rec
    print(e['order'], e['station'], rec['t_obs_src'], rec['anchor'], 'end', rec['end'], {L: (v['t0'][5:13], v['length_h']) for L, v in rec['leads'].items()}, 'crop', rec['domain']['crop_lat'], rec['domain']['crop_lon_west_neg'])
json.dump(out, open(sys.argv[3], 'w'), indent=1)
