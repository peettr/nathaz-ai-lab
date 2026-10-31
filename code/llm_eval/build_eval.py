import csv, gzip, io, json, random, re, sqlite3, requests
from pathlib import Path
ROOT=Path('./'); OUT=Path(__file__).parent
WIKI=ROOT/'16_PETW/05_Literature_Wiki/wiki'; rng=random.Random(20261013)
con=sqlite3.connect('file:./Zotero/zotero.sqlite?immutable=1',uri=True)
def item(f):
 s=f.read_text(errors='replace'); m=re.search(r'(?:Zotero key|zotero_key):\s*`?([A-Z0-9]{8})',s,re.I)
 if not m:return None
 row=con.execute('select itemID from items where key=?',(m[1],)).fetchone()
 if not row:return None
 d=dict(con.execute('select f.fieldName,v.value from itemData d join fields f using(fieldID) join itemDataValues v using(valueID) where d.itemID=? and f.fieldName in ("abstractNote","title")',(row[0],)).fetchall())
 if len(d.get('abstractNote',''))<180:return None
 return m[1],d
rows=[]
pos=[]; neg=[]
for f in (WIKI/'cfd_m4_downburst_cfd/paper_cards').glob('*.md'):
 r=item(f)
 if r and re.search(r'downburst|thunderstorm|microburst',r[1]['title']+' '+r[1]['abstractNote'],re.I) and re.search(r'downburst|thunderstorm|microburst',r[1]['title'],re.I):pos.append((f,r))
for f in (WIKI/'cfd_m1_general_cwe/paper_cards').glob('*.md'):
 r=item(f)
 if r and not re.search(r'downburst|thunderstorm|microburst',r[1]['title']+' '+r[1]['abstractNote'],re.I):neg.append((f,r))
for f in (WIKI/'wrf_mesoscale_modeling').rglob('*.md'):
 r=item(f)
 if r and not re.search(r'downburst|thunderstorm|microburst',r[1]['title']+' '+r[1]['abstractNote'],re.I):neg.append((f,r))
print('A candidates',len(pos),len(neg),flush=True)
assert len(pos)>=10 and len(neg)>=30
rng.shuffle(pos);rng.shuffle(neg)
for label,chosen in [('是',pos[:10]),('否',neg[:30])]:
 for f,(key,d) in chosen:
  rows.append(dict(group='A',id=f'A{len([r for r in rows if r["group"]=="A"])+1:02}',prompt='依据标题和摘要，判定是否属于下击暴流/雷暴出流风场的模拟或观测研究。只回答 JSON：{"answer":"是"或"否"}。\n标题：'+d['title']+'\n摘要：'+re.sub(r'<[^>]+>',' ',d['abstractNote'])[:3500],answer=label,source=str(f),source_key=key))
# NCEI 2024 details: download official yearly gzip; hide EVENT_TYPE, filter obvious type leakage in narrative.
u='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
html=requests.get(u,timeout=40).text
links=re.findall(r'StormEvents_details-ftp_v1\.0_d2024_c\d+\.csv\.gz',html);assert links
url=u+sorted(set(links))[-1]
response=requests.get(url,timeout=90);response.raise_for_status()
raw=list(csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(response.content)),encoding='utf-8',errors='replace')))
classes={'Thunderstorm Wind':'Thunderstorm Wind','High Wind':'High Wind','Strong Wind':'Strong Wind'}
candidates={k:[] for k in [*classes,'其他']}
for r in raw:
 typ=r['EVENT_TYPE'];label=classes.get(typ,'其他'); text=r.get('EVENT_NARRATIVE','').strip()
 if len(text)<140 or len(text)>1100:continue
 if re.search(r'\b(thunderstorm wind|high wind|strong wind|event type)\b',text,re.I):continue
 if label=='其他' and typ not in ['Tornado','Hail','Flash Flood','Winter Storm','Blizzard','Heavy Rain']:continue
 candidates[label].append(r)
for label,n in [('Thunderstorm Wind',7),('High Wind',5),('Strong Wind',4),('其他',4)]:
 assert len(candidates[label])>=n,(label,len(candidates[label]))
 for r in rng.sample(candidates[label],n):
  rows.append(dict(group='C',id=f'C{len([x for x in rows if x["group"]=="C"])+1:02}',prompt='根据 NOAA Storm Events 事件描述判别类型。仅回答 JSON：{"answer":"Thunderstorm Wind/High Wind/Strong Wind/其他"}，从四类中选一个。\n描述：'+r['EVENT_NARRATIVE'].strip(),answer=label,source=url+'#EVENT_ID='+r['EVENT_ID'],event_id=r['EVENT_ID'],original_event_type=r['EVENT_TYPE']))
# D numerical regression values, no unpublished papers; candidate calculator benchmark not design-approved.
f=ROOT/'16_PETW/02_Subprojects/Design_Load/outputs/GFF_Implementation_20260807/full_time_frequency_i3_benchmark_v1.json';bench=json.loads(f.read_text());assert len(bench['cases'])>=8
for i,c in enumerate(bench['cases'][:12]):
 a,b=c['max_sigma_x'],c['peak_local_sigma_x'];value=c['full_vs_peak_local_response_ratio'];assert abs(a/b-value)<1e-10
 rows.append(dict(group='D',id=f'D{i+1:02}',prompt=f'候选阵风/时频响应计算的回归单点：完整时频最大响应标准差为 {a:.12g}，峰值局部响应标准差为 {b:.12g}。计算两者比值（无量纲），保留至少 4 位小数。仅答 JSON：{{"answer":数字}}。',answer=value,source=str(f)+'#cases['+str(i)+'].full_vs_peak_local_response_ratio',unit='1'))
# The three lock-only lookups are excluded because the JSON values were not supplied to models; instead use three additional fully specified ratio cases below.
for j,c in enumerate(bench['cases'][:4]):
 a,b=c['max_sigma_q'],c['max_sigma_x'];value=a/b
 rows.append(dict(group='D',id=f'D{9+j:02}',prompt=f'候选计算器回归单点：最大广义荷载标准差 {a:.12g}，最大响应标准差 {b:.12g}。求前者除以后者的无量纲比值（至少 4 位小数）。仅答 JSON：{{"answer":数字}}。',answer=value,source=str(f)+'#cases['+str(j)+'].max_sigma_q/max_sigma_x',unit='1'))
for j,c in enumerate(bench['cases'][4:7],start=13):
 a,b=c['max_sigma_q'],c['max_sigma_x'];value=a/b
 rows.append(dict(group='D',id=f'D{j:02}',prompt=f'候选计算器回归单点：最大广义荷载标准差 {a:.12g}，最大响应标准差 {b:.12g}。求前者除以后者的无量纲比值（至少 4 位小数）。仅答 JSON：{{"answer":数字}}。',answer=value,source=str(f)+'#cases['+str(j-13+4)+'].max_sigma_q/max_sigma_x',unit='1'))
# B handled separately after PDF-to-text page verification; do not create card-only leakage.
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'eval_partial.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
print('generated',len(rows),'C source',url,'counts',{g:sum(r['group']==g for r in rows) for g in 'ACD'},flush=True)
