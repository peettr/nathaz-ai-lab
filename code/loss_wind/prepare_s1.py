#!/usr/bin/env python3
"""Reproducible S1 supplementary cohort from official NCEI yearly details."""
import csv, gzip, hashlib, json, pathlib, random, urllib.request, collections
P=pathlib.Path(__file__).parent
S=pathlib.Path('./16_PETW/02_Subprojects/SP1_Event_Classification_Reconstruction/07_Outputs/S1_Detectability_TX4_20261009/S1_ROWS_v1.2.csv')
C=pathlib.Path('./.hermes/profiles/researchos-lab-ideas/cache/scratch/loss_wind_ncei')
C.mkdir(parents=True,exist_ok=True)
refs={x['event_id'].split(':',1)[1]:x for x in csv.DictReader(S.open()) if x['source_lane']=='StormEvents'}
# Fixed-seed candidate order; gather matches in source year, then choose eligible forty.
urls=collections.defaultdict(set)
for id,x in refs.items():urls[int(x['event_window_start_utc'][:4])].add(x['event_source_uri'])
matched={}; provenance=[]
for year, links in sorted(urls.items()):
 assert len(links)==1,(year,links)
 url=links.pop(); dest=C/pathlib.Path(url).name
 if not dest.exists():urllib.request.urlretrieve(url,dest)
 digest=hashlib.sha256(dest.read_bytes()).hexdigest()
 provenance.append(dict(year=year,url=url,sha256=digest,bytes=dest.stat().st_size))
 with gzip.open(dest,'rt',newline='',errors='replace') as f:
  for row in csv.DictReader(f):
   id=row['EVENT_ID']
   if id in refs and row['EVENT_TYPE']=='Thunderstorm Wind' and (row['EVENT_NARRATIVE'] or '').strip():matched[id]=(row,refs[id])
print('matched eligible',len(matched),'by year',collections.Counter(int(r['event_window_start_utc'][:4]) for _,r in matched.values()))
assert len(matched)>=40
picked=random.Random(20261014).sample(sorted(matched),40)
keys=['EVENT_ID','hazard','year','s1_overlap','s1_city','EVENT_TYPE','BEGIN_DATE_TIME','END_DATE_TIME','CZ_TIMEZONE','STATE','CZ_NAME','BEGIN_LOCATION','BEGIN_LAT','BEGIN_LON','END_LAT','END_LON','EVENT_NARRATIVE','MAGNITUDE','MAGNITUDE_TYPE','SOURCE','DAMAGE_PROPERTY']
with (P/'sample_4.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
 for id in picked:
  row,ref=matched[id];w.writerow({**{k:row.get(k,'') for k in keys},'hazard':'thunderstorm','year':ref['event_window_start_utc'][:4],'s1_overlap':True,'s1_city':ref['city']})
with (P/'questions_4.jsonl').open('w') as f:
 for id in picked:f.write(json.dumps({'id':id,'prompt':'EVENT_NARRATIVE:\n'+matched[id][0]['EVENT_NARRATIVE']},ensure_ascii=False)+'\n')
(P/'source_provenance_s1.json').write_text(json.dumps({'seed':20261014,'s1_source':str(S),'s1_sha256':hashlib.sha256(S.read_bytes()).hexdigest(),'source':provenance,'eligible':len(matched),'selected':40},indent=2)+'\n')
(P/'claude_review_ids_4.json').write_text(json.dumps(random.Random(20261018).sample(picked,4),indent=2)+'\n')
print('written 40, years',collections.Counter(matched[id][1]['event_window_start_utc'][:4] for id in picked))
