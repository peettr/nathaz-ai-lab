#!/usr/bin/env python3
"""Add per-station event-window gust maximum alongside nearest-time gust, without changing r2."""
import csv, datetime as D, pathlib, statistics, json, re
from collections import defaultdict
P=pathlib.Path(__file__).parent
pairs=list(csv.DictReader((P/'dat_iem_pairs_r2.csv').open()))
obs={}
for case in set(x['case'] for x in pairs):
    by=defaultdict(list)
    with (P/f'iem_gust_{case}.csv').open() as f:
        for r in csv.DictReader(f):
            try:by[r['station']].append((D.datetime.fromisoformat(r['valid']).replace(tzinfo=D.timezone.utc),float(r['gust'])))
            except (ValueError,KeyError):pass
    obs[case]=by
out=[]
for r in pairs:
    t=D.datetime.fromisoformat(r['dat_utc']);w=D.timedelta(hours=12 if r['case'].startswith(('Ian','Ida')) else 3)
    valid=[(ot,g) for ot,g in obs[r['case']][r['station']] if abs(ot-t)<=w]
    if not valid:raise RuntimeError('missing observation '+r['objectid'])
    peak_time,peak=max(valid,key=lambda x:(x[1],-abs((x[0]-t).total_seconds())))
    r['max_gust_kt']=peak;r['max_utc']=peak_time.isoformat();r['max_minus_nearest_kt']=peak-float(r['gust_kt']);r['gust_over_100kt']=(peak>100 or float(r['gust_kt'])>100)
    m=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*',r['dat_windspeed_damage_inferred'] or '')
    dat=float(m.group(1)) if m and float(m.group(1))>0 else None
    r['dat_numeric_mph']=dat;r['nearest_mph']=float(r['gust_kt'])*1.150779448;r['max_mph']=peak*1.150779448
    r['dat_minus_nearest_mph']=dat-r['nearest_mph'] if dat is not None else None
    r['dat_minus_max_mph']=dat-r['max_mph'] if dat is not None else None
    out.append(r)
path=P/'dat_iem_pairs_r2_augmented.csv'
if path.exists():raise FileExistsError(path)
with path.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
summary=[]
for case in sorted(set(r['case'] for r in out)):
    rr=[r for r in out if r['case']==case];d=[float(r['max_minus_nearest_kt']) for r in rr]
    summary.append({'case':case,'paired_points':len(rr),'max_above_nearest_count':sum(z>0 for z in d),'median_max_minus_nearest_kt':statistics.median(d),'max_max_minus_nearest_kt':max(d),'over_100kt_points':sum(r['gust_over_100kt'] for r in rr)})
path=P/'demo_max_summary_r2.json'
if path.exists():raise FileExistsError(path)
path.write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
