#!/usr/bin/env python3
"""Count existing H2 hourly-observation survivors within 150 km; no model pairing."""
import csv, math
from collections import defaultdict
from pathlib import Path
P=Path(__file__).resolve().parent
H=P.parent/'obs_fusion'/'h2'
events=list(csv.DictReader((P/'events_verified.csv').open()))
passed=defaultdict(set)
for fn in ('peaks_h2_expanded.csv','peaks_francine_h2f.csv'):
 for r in csv.DictReader((H/fn).open()):passed[r['event']].add(r['station'].split(':')[-1])
rows=[]
for e in events:
 name=e['name']; n=name.lower(); sp=H/f'stations_{n}_expanded.csv'
 if not sp.exists():sp=H/f'stations_{n}_h2.csv'
 if not sp.exists():sp=H/'stations_francine_h2f.csv'
 a,b=float(e['lat']),float(e['lon']); near=set()
 for r in csv.DictReader(sp.open()):
  c,d=float(r['lat']),float(r['lon'])
  x=math.sin(math.radians(c-a)/2)**2+math.cos(math.radians(a))*math.cos(math.radians(c))*math.sin(math.radians(d-b)/2)**2
  if 12742*math.asin(min(1,math.sqrt(x)))<=150:near.add(r['station'].split(':')[-1])
 rows.append({'event':name,'h2_candidate_150km':len(near),'h2_hourly_survivors_150km':len(near&passed[name]),'h2_source':sp.name,'ofcl_48_cycle':'missing' if name=='NICHOLAS' else 'present_s2b'})
with (P/'v2_existing_h2_150km.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
print(*rows,sep='\n')
