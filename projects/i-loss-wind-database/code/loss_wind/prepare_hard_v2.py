#!/usr/bin/env python3
"""Replace weak candidate-discovery damage stratum with hand-screened explicit cases."""
import csv,gzip,pathlib
P=pathlib.Path(__file__).parent;RAW=pathlib.Path('./.hermes/profiles/researchos-lab-ideas/cache/scratch/loss_wind_ncei')
ids=['954704','975490','976555','979361','985286','976648','976639','976253','982087','976643','1000842','988481','994189','1095670','953276']
rows=[]
for r in csv.DictReader((P/'sample_hard_70.csv').open()):
 if r['stratum']!='damage_wind':rows.append(r)
found={}
for f in RAW.glob('*.csv.gz'):
 if not any('d'+str(y) in f.name for y in range(2018,2024)):continue
 with gzip.open(f,'rt',encoding='utf-8-sig',errors='replace',newline='') as z:
  for r in csv.DictReader(z):
   if r['EVENT_ID'] in ids:found[r['EVENT_ID']]=r
assert len(found)==15
for id in ids:
 r=found[id];rows.append({**{k:r.get(k,'') for k in rows[0]},'EVENT_ID':id,'stratum':'damage_wind'})
assert len(rows)==len({x['EVENT_ID'] for x in rows})==70
cols=list(rows[0]);
with (P/'sample_hard_70_v2.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,cols);w.writeheader();w.writerows(rows)
print('70 distinct; explicit damage set',ids)
