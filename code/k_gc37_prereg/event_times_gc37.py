#!/usr/bin/env python3
"""Anchor, windows, init times, integration lengths for GC37 events (prereg v2 items 4, 11).
t_obs = METAR 'PK WND dddff/(hh)mm' time if present else report time; anchor = t_obs rounded to nearest 10 min.
Windows: existence [a-3h, a+3h], first-onset search [a-6h, a+3h], endpoints included.
t0(L) = floor(a to 6h) - L, L in 24/48/72 h; end = first 6-h boundary >= a+3h.
Usage: python3 -I event_times_gc37.py events_selected_gc37.json out.json"""
import json, re, sys
from datetime import datetime, timedelta
ev = json.load(open(sys.argv[1]))
def pk(e):
    t = datetime.fromisoformat(e['utc'])
    m = re.search(r'PK WND \d{5,6}/(\d{2})?(\d{2})', e.get('metar', ''))
    if not m: return t, 'report_time'
    hh = int(m.group(1)) if m.group(1) else t.hour
    c = t.replace(hour=hh, minute=int(m.group(2)), second=0)
    if c > t + timedelta(hours=1): c -= timedelta(days=1)
    return c, 'PK_WND'
out = {}
for k in ['E1', 'E2', 'E3', 'R1', 'R2']:
    e = ev[k]
    if k == 'E1': t, src = datetime.fromisoformat(e['utc']), 'Childs2021_KAKO'
    else: t, src = pk(e)
    a = datetime(t.year, t.month, t.day, t.hour) + timedelta(minutes=10 * round((t.minute + t.second / 60) / 10))
    f6 = a.replace(minute=0) - timedelta(hours=a.hour % 6)
    end = a + timedelta(hours=3); 
    if end.minute or end.hour % 6: end = end.replace(minute=0) + timedelta(hours=(6 - end.hour % 6) % 6 or (6 if end.minute else 0))
    rec = {'station': e['station'], 't_obs': t.isoformat(), 't_obs_src': src, 'anchor': a.isoformat(),
           'exist_win': [(a - timedelta(hours=3)).isoformat(), (a + timedelta(hours=3)).isoformat()],
           'onset_win': [(a - timedelta(hours=6)).isoformat(), (a + timedelta(hours=3)).isoformat()],
           'end': end.isoformat(), 'leads': {}}
    for L in (24, 48, 72):
        t0 = f6 - timedelta(hours=L)
        rec['leads'][f'{L}h'] = {'t0': t0.isoformat(), 'length_h': (end - t0).total_seconds() / 3600}
    out[k] = rec
    print(k, rec['station'], src, rec['anchor'], 'end', rec['end'], {L: (v['t0'][5:13], v['length_h']) for L, v in rec['leads'].items()})
json.dump(out, open(sys.argv[2], 'w'), indent=1)
