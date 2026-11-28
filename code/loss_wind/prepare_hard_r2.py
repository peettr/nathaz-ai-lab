#!/usr/bin/env python3
"""Freeze disjoint candidate strata; regex is only candidate discovery, never gold."""
import csv,gzip,json,random,re,pathlib,collections
P=pathlib.Path(__file__).parent; RAW=pathlib.Path('./.hermes/profiles/researchos-lab-ideas/cache/scratch/loss_wind_ncei')
prior={r['EVENT_ID'] for i in range(1,4) for r in csv.DictReader((P/f'sample_{i}.csv').open())}
patterns=[('thunder_EG_numeric',20,lambda r,t:r['EVENT_TYPE']=='Thunderstorm Wind' and r['MAGNITUDE_TYPE']=='EG' and bool(re.search(r'\b\d{2,3}\s*(?:to|-|–)?\s*\d{0,3}\s*(?:mph|kts?|knots)\b',t,re.I))),('thunder_MG',10,lambda r,t:r['EVENT_TYPE']=='Thunderstorm Wind' and r['MAGNITUDE_TYPE']=='MG' and bool(re.search(r'\b\d{2,3}\s*(?:mph|kts?|knots)\b',t,re.I))),('tropical_station',15,lambda r,t:r['EVENT_TYPE'] in ('Hurricane (Typhoon)','Tropical Storm') and bool(re.search(r'\b(?:ASOS|AWOS|mesonet|station|anemometer|airport|buoy|measured|recorded)\b',t,re.I)) and bool(re.search(r'\b\d{2,3}\s*(?:mph|kts?|knots)\b',t,re.I))),('high_wind_station',10,lambda r,t:r['EVENT_TYPE']=='High Wind' and bool(re.search(r'\b(?:ASOS|AWOS|mesonet|station|anemometer|airport|measured|recorded)\b',t,re.I)) and bool(re.search(r'\b\d{2,3}\s*(?:mph|kts?|knots)\b',t,re.I))),('damage_wind',15,lambda r,t:r['EVENT_TYPE'] in ('Thunderstorm Wind','High Wind','Hurricane (Typhoon)','Tropical Storm') and bool(re.search(r'(?:estimated|estimate|suggest|indic|represent|based on).{0,75}(?:damag|trees?|EF[0-5]|wind|mph)|(?:damag|trees?|EF[0-5]).{0,75}(?:estimated|estimate|indic|wind|mph)',t,re.I)) and bool(re.search(r'\b\d{2,3}\s*(?:mph|kts?|knots)\b',t,re.I)))]
pools={k:[] for k,_,_ in patterns}
for item in json.loads((P/'source_provenance.json').read_text()):
 file=RAW/pathlib.Path(item['url']).name
 with gzip.open(file,'rt',encoding='utf-8-sig',errors='replace',newline='') as f:
  for r in csv.DictReader(f):
   if r['EVENT_ID'] in prior:continue
   t=(r.get('EVENT_NARRATIVE') or '').strip()
   if not t:continue
   for k,n,fn in patterns:
    if fn(r,t):pools[k].append(r)
rng=random.Random(20261016);used=set(prior);chosen=[]
for k,n,_ in patterns:
 pool=pools[k];rng.shuffle(pool);subset=[]
 for r in pool:
  if r['EVENT_ID'] in used:continue
  subset.append(r);used.add(r['EVENT_ID'])
  if len(subset)==n:break
 chosen.extend([{**r,'stratum':k} for r in subset]);print(k,len(pool),len(subset))
assert len(chosen)==70 and len({r['EVENT_ID'] for r in chosen})==70
cols=['EVENT_ID','stratum','EVENT_TYPE','BEGIN_DATE_TIME','STATE','MAGNITUDE','MAGNITUDE_TYPE','EVENT_NARRATIVE']
with (P/'sample_hard_70.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows({k:r.get(k,'') for k in cols} for r in chosen)
(P/'hard_candidate_sheet.txt').write_text('\n\n'.join(f"{r['EVENT_ID']} | {r['stratum']} | {r['MAGNITUDE_TYPE']} {r['MAGNITUDE']} | {r['EVENT_NARRATIVE']}" for r in chosen)+'\n')
