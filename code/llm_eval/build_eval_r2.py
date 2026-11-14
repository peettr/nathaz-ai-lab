"""Build frozen round-two public-source evaluation; never read old builders as modules."""
import csv, gzip, io, json, random, re, sqlite3, urllib.request
from pathlib import Path
ROOT=Path('./'); OUT=Path(__file__).parent
WIKI=ROOT/'16_PETW/05_Literature_Wiki/wiki'; rng=random.Random(20261013)
con=sqlite3.connect('file:./Zotero/zotero.sqlite?immutable=1',uri=True)
def metadata(f):
 s=f.read_text(errors='replace');m=re.search(r'(?:Zotero key|zotero_key):\s*`?([A-Z0-9]{8})',s,re.I)
 if not m:return None
 q=con.execute('select itemID from items where key=?',(m[1],)).fetchone()
 if not q:return None
 d=dict(con.execute('select f.fieldName,v.value from itemData d join fields f using(fieldID) join itemDataValues v using(valueID) where d.itemID=? and f.fieldName in ("abstractNote","title")',q).fetchall())
 a=re.sub(r'<[^>]+>',' ',d.get('abstractNote','')).strip()
 if len(a)<200:return None
 return m[1],d.get('title',''),a
seen=set();pos=[];neg=[]
# Read core field-study libraries first; duplicate Zotero keys in other libraries are not independent examples.
files=list((WIKI/'cfd_m4_downburst_cfd/paper_cards').glob('*.md'))+list((WIKI/'windfield_step2/papers').glob('*.md'))+list(WIKI.rglob('*.md'))
for f in files:
 area=f.relative_to(WIKI).parts[0]
 if area not in {'cfd_m4_downburst_cfd','cfd_m1_general_cwe','wrf_mesoscale_modeling','eva_vhat3s','wt_m1_accelerating_flow','windfield_step2','step1_cm1','liang2_shared_library','cfd_m3_accelerating_flow','designload_step5','step4c_structural_response'}:continue
 r=metadata(f)
 if not r or r[0] in seen:continue
 seen.add(r[0]);key,title,abstract=r; a=abstract.lower(); t=title.lower()
 # Exclude reviews, load/structural-only articles and generic thunderstorms from positive class.
 if area in ('cfd_m4_downburst_cfd','windfield_step2') and re.search(r'downburst|microburst|thunderstorm|macroburst|gust front',t) and re.search(r'field|flow|velocity|wind speed|simulation|measurement|observation',a) and not re.search(r'\breview\b|loading|response|fragility|damage|pressure|gust factor|hazard|extreme value|load effects|load calculation',t):
  pos.append((f,key,title,abstract))
 elif area!='cfd_m4_downburst_cfd':
  # Hard negatives include discussions of thunderstorm winds, when the actual work is loads/statistics/methods, not field simulation/observation.
  if re.search(r'wind|storm|turbulen|weather|cwe|boundary layer|wrf|cfd|building',a):neg.append((f,key,title,abstract))
print('A candidate pools',len(pos),len(neg),flush=True)
# Manual title/abstract adjudication before any baseline/model run; do not count pressure/load-only papers as field studies.
not_field={'WVGZ39GL','HM96CD7L','UT8ZUPS5','TXR6JST2','FFREEQCW','WW2JLHT7','DWWTLFF6','STEG93YR','BLG2PYL6','Z454567N'}
actual_field={'H4VP54G9','G7E2KVJN','TZL5NJZY','PFUI922G','KYSQSJZT','QTSGU7NN','9LSY8I27','3PBTHS5N','BYQ2L3DI','AMW39TYF','N96SJZZL','FUDJEEZK','8XIJBMBP','NHQTYZH2','U4DZZRWT','GZYPXN4S','3GMQ924C'}
pos=[x for x in pos if x[1] not in not_field]
neg=[x for x in neg if x[1] not in actual_field and x[1] not in not_field]
print('after manual exclusions',len(pos),len(neg),flush=True)
assert len(pos)>=50 and len(neg)>=150
# Prefer topical negative pools, cap any one collection; randomized within collection.
by={}
for x in neg:by.setdefault(x[0].relative_to(WIKI).parts[0],[]).append(x)
for x in by.values():rng.shuffle(x)
quotas={'cfd_m1_general_cwe':10,'wrf_mesoscale_modeling':10,'eva_vhat3s':21,'wt_m1_accelerating_flow':26,'windfield_step2':17,'step1_cm1':4,'liang2_shared_library':8,'cfd_m3_accelerating_flow':3,'designload_step5':15,'step4c_structural_response':36}
assert sum(quotas.values())==150
assert all(len(by.get(k,[]))>=v for k,v in quotas.items()),{k:(v,len(by.get(k,[]))) for k,v in quotas.items()}
rng.shuffle(pos);chosen=[('是',x) for x in pos[:50]]+ [('否',x) for k,v in quotas.items() for x in by[k][:v]];rng.shuffle(chosen)
rows=[]
for i,(label,(f,key,title,abstract)) in enumerate(chosen,1):
 rows.append(dict(group='A2',id=f'A2_{i:03}',prompt='仅依据下列已发表论文摘要，判断它本身是否研究下击暴流/雷暴出流风场的模拟或观测（非只研究建筑荷载、灾害统计或一般雷暴）。只输出 JSON：{"answer":"是"} 或 {"answer":"否"}。\n摘要：'+abstract[:3500],answer=label,source=str(f),source_key=key,title_hidden=title))
# Official NOAA yearly event-detail CSVs; no unpublished event material.
base='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
html=urllib.request.urlopen(base,timeout=60).read().decode()
urls={}
for y in [2019,2021,2023,2024]:
 names=sorted(set(re.findall(r'StormEvents_details-ftp_v1\.0_d'+str(y)+r'_c\d+\.csv\.gz',html)))
 assert names,y;urls[y]=base+names[-1]
cs={'Thunderstorm Wind':[], '非对流性大风':[]}
for y,url in urls.items():
 data=urllib.request.urlopen(url,timeout=120).read()
 for r in csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(data)),encoding='utf-8',errors='replace')):
  typ=r.get('EVENT_TYPE');txt=r.get('EVENT_NARRATIVE','').strip();state=r.get('STATE','')
  if typ not in ('Thunderstorm Wind','High Wind','Strong Wind') or not (140<=len(txt)<=1400):continue
  # Predeclared ambiguity exclusions, not tuned on model answers. Generic damage-only narratives cannot determine convective vs synoptic cause.
  if re.search(r'\b(thunderstorm wind|high wind|strong wind)\b',txt,re.I):continue
  low=txt.lower()
  conv=bool(re.search(r'\b(thunderstorm|tstm|t-storm|convective|squall line|downburst|microburst|supercell|outflow boundary|storm cell)\b',low))
  nonconv=bool(re.search(r'\b(frontal|cold front|pressure gradient|synoptic|non-convective|nonconvective|mountain wave|gradient winds?|post-frontal|gap winds?)\b',low))
  if typ=='Thunderstorm Wind' and (not conv or nonconv):continue
  if typ!='Thunderstorm Wind' and (not nonconv or conv):continue
  cs['Thunderstorm Wind' if typ=='Thunderstorm Wind' else '非对流性大风'].append((y,url,r))
 print('C',y,len(cs['Thunderstorm Wind']),len(cs['非对流性大风']),flush=True)
# Stratify across years and states; unique event id. Select 50 each via round-robin year and state diversity.
selected=[]
for label,pool in cs.items():
 byyear={y:[] for y in urls}
 for item in pool:byyear[item[0]].append(item)
 for y,v in byyear.items():rng.shuffle(v)
 assert all(len(v)>=12 for v in byyear.values()),{y:len(v) for y,v in byyear.items()}
 counts={};target={2019:13,2021:12,2023:13,2024:12}
 for y,n in target.items():
  arr=byyear[y];prior=set()
  while n:
   cand=next((x for x in arr if x[2]['STATE'] not in prior and counts.get(x[2]['STATE'],0)<4),None)
   if cand is None:cand=next((x for x in arr if counts.get(x[2]['STATE'],0)<4),None)
   assert cand is not None,(label,y,n)
   arr.remove(cand);selected.append((label,cand));prior.add(cand[2]['STATE']);counts[cand[2]['STATE']]=counts.get(cand[2]['STATE'],0)+1;n-=1
rng.shuffle(selected)
for i,(label,(y,url,r)) in enumerate(selected,1):
 rows.append(dict(group='C2',id=f'C2_{i:03}',prompt='仅根据 NOAA Storm Events 事件叙述，判断是雷暴阵风（Thunderstorm Wind）还是非对流性大风（High Wind/Strong Wind）。只输出 JSON：{"answer":"Thunderstorm Wind"} 或 {"answer":"非对流性大风"}。\n叙述：'+r['EVENT_NARRATIVE'].strip(),answer=label,source=url+'#EVENT_ID='+r['EVENT_ID'],event_id=r['EVENT_ID'],year=y,state=r['STATE'],original_event_type=r['EVENT_TYPE']))
assert len(rows)==300 and len({r['id'] for r in rows})==300
(OUT/'eval_ac_r2_draft.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
print('AC READY',len(rows),'states',len({r['state'] for r in rows if r['group']=='C2'}),flush=True)
