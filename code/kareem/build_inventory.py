#!/usr/bin/env python3
"""Read-only metadata inventory; outputs solely in this directory."""
import csv,sqlite3,re,unicodedata,collections,os,json,urllib.request,time
from pathlib import Path
OUT=Path(__file__).parent
META=Path('./22_Lab/06_Logs/fulltext_kb/desktop_inventory/metadata')
INDEX='./services/ftkb/data/index.sqlite'
ZOT='./Zotero/zotero.sqlite'
def ro(p):
 c=sqlite3.connect('file:'+p+'?mode=ro',uri=True); c.row_factory=sqlite3.Row; return c
def norm(s): return re.sub(r'[^a-z0-9]+','',unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower())
def doi(s): return re.sub(r'^https?://(?:dx\.)?doi\.org/','',(s or '').strip().lower()).strip(' .')
def year(s):
 m=re.search(r'(?<!\d)(?:18|19|20)\d\d(?!\d)',str(s or '')); return m.group() if m else ''
def names(s):
 if not s:return []
 return [x.strip() for x in re.split(r'\s*;\s*',s) if x.strip()]
def desktop_names(s):
 if ';' in s:return names(s)
 parts=re.split(r'(?i)\s+(?:and|&)\s+',s)
 out=[]
 for part in parts:
  part=part.strip(' ,')
  seg=part.split(', ')
  if len(seg)<2:out.append(part)
  elif re.match(r'^[A-Z][A-Za-z-]+$',seg[0]) and re.match(r'^[A-Z](?:\.|[a-z]+)',seg[1]):
   out.extend(', '.join(seg[i:i+2]) for i in range(0,len(seg),2))
  else:out.extend(seg)
 return [x.strip(' ,') for x in out if x.strip(' ,')]
def kpos(arr):
 return next((i+1 for i,x in enumerate(arr) if re.search(r'\bkareem\b',x,re.I)),None)
def readcsv(n): return list(csv.DictReader(open(META/n,encoding='utf-8-sig',newline='')))
idx=ro(INDEX)
aidx=[dict(r) for r in idx.execute('select * from attachments') if 'kareem' in (r['authors'] or '').lower()]
bykey=collections.defaultdict(list)
for a in aidx: bykey[(a['library'],a['key'])].append(a)
z=ro(ZOT)
fields={r['fieldID']:r['fieldName'] for r in z.execute('select fieldID,fieldName from fields')}
zitems=collections.defaultdict(dict)
for r in z.execute('select d.itemID,d.fieldID,v.value from itemData d join itemDataValues v on d.valueID=v.valueID'):
 if r['fieldID'] in fields:zitems[r['itemID']][fields[r['fieldID']]]=r['value']
rows=[]
q='''select i.itemID,i.key,t.typeName,c.firstName,c.lastName,ic.orderIndex from items i join itemCreators ic on ic.itemID=i.itemID join creators c on c.creatorID=ic.creatorID join itemTypes t on t.itemTypeID=i.itemTypeID order by i.itemID,ic.orderIndex'''
people=collections.defaultdict(list); ztype={}; zkeys={}
for r in z.execute(q):
 people[r['itemID']].append((' '.join(filter(None,[r['firstName'],r['lastName']]))).strip()); zkeys[r['itemID']]=r['key']; ztype[r['itemID']]=r['typeName']
for iid,pp in people.items():
 if not kpos(pp):continue
 key=zkeys[iid]; f=zitems[iid]; attached=bykey.get(('Zotero',key),[])
 # Index stores one record per PDF attachment; metadata comes from parent rather than abbreviated indexed authors.
 att=[dict(a) for a in z.execute('select i.key,ia.path,ia.contentType from itemAttachments ia join items i on i.itemID=ia.itemID where ia.parentItemID=?',(iid,)) if a['contentType']=='application/pdf']
 pdfs=[]
 for a in att:
  path=a['path'] or ''
  if path.startswith('storage:'): path=f'./Zotero/storage/{a["key"]}/'+path[8:]
  pdfs.append(path)
 rows.append(dict(lib='Zotero',id=key,title=f.get('title',''),year=year(f.get('date')),venue=f.get('publicationTitle') or f.get('proceedingsTitle') or f.get('bookTitle') or '',authors=pp,doi=doi(f.get('DOI')),sha=[a['sha256'] for a in attached if a['sha256']],pdf=pdfs,pages=max([a['n_pages'] or 0 for a in attached],default=0),has=any(os.path.isfile(p) for p in pdfs),note='' if f.get('title') else '缺 Zotero 题名'))
end=readcsv('endnote_records_v3.csv')
# Include indexed EndNote records even when local parsed author list was incomplete.
endkeys={a['key'] for a in aidx if a['library']=='EndNote'}
for e in end:
 pp=names(e['authors']); keys=[e['record_id']]+[x for x in e['end_keys'].split(';') if x]
 if not kpos(pp) and not (endkeys & set(keys)):continue
 matching=[a for key in keys for a in bykey.get(('EndNote',key),[])]
 if not kpos(pp): pp=names(matching[0]['authors']) if matching else []
 if not kpos(pp):continue
 paths=[x.strip() for x in e['pdf_paths'].split(';') if x.strip()]
 rows.append(dict(lib='EndNote',id=e['record_id'],extra=e['end_keys'],title=e['title'] or (matching[0]['title'] if matching else ''),year=year(e['year'] or (matching[0]['year'] if matching else '')),venue=e['journal'] or (matching[0]['container'] if matching else ''),authors=pp,doi=doi(e['doi_verified_join'] or e['doi']),sha=[a['sha256'] for a in matching if a['sha256']],pdf=paths,pages=max([a['n_pages'] or 0 for a in matching],default=0),has=any(os.path.isfile(p) for p in paths) or bool(matching),note='作者据索引补全' if not kpos(names(e['authors'])) else ''))
desk=readcsv('desktop_records_v3.csv')
deskkeys={a['key'] for a in aidx if a['library']=='Desktop'}
for d in desk:
 key='DSK-'+d['sha256'][:16]; pp=desktop_names(d['authors'])
 if not kpos(pp) and key not in deskkeys:continue
 matching=bykey.get(('Desktop',key),[])
 if not kpos(pp):pp=names(matching[0]['authors']) if matching else []
 if not kpos(pp):continue
 if re.search(r'\bvita[-_ ]|curriculum vitae',d['title'],re.I):continue # CV is not a scholarly work
 # Original desktop file is remote; do not claim local accessibility.
 good=d['confidence'] not in ('low_home','low_filename','')
 title=d['title'] if good else (matching[0]['title'] if matching and matching[0]['title'] else d['title'])
 dy=year(d['year'] or (matching[0]['year'] if matching else ''))
 if ('Microsoft PowerPoint' in title and dy and int(dy)<1980):dy=''
 rows.append(dict(lib='Desktop',id=key,title=title,year=dy,venue=(matching[0]['container'] if matching else ''),authors=pp,doi=doi(d['doi_verified_join']),sha=[d['sha256']],pdf=[d['windows_paths']],pages=int(d['pages'] or 0),has=True,note=('题名仅文件名/首页候选；须核原件' if not good else '')+'；远端 I 盘全文未本机核验'))
# Union-find, only DOI/title+year/hash, and refuse metadata contradictions.
parent=list(range(len(rows))); reason=collections.defaultdict(set)
def root(i):
 while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
 return i
def merge(i,j,why):
 x,y=root(i),root(j)
 if x==y:return
 left=[rows[k] for k in range(len(rows)) if root(k)==x];right=[rows[k] for k in range(len(rows)) if root(k)==y]
 ds={r['doi'] for r in left+right if r['doi']}
 if len(ds)>1:
  rows[i]['note']+='；疑似同作但 DOI 冲突';rows[j]['note']+='；疑似同作但 DOI 冲突';return
 parent[y]=x;reason[x]|=reason[y]|{why}
for i,r in enumerate(rows):
 for j in range(i):
  s=rows[j]; why=''
  if r['doi'] and r['doi']==s['doi']:why='DOI'
  elif r['title'] and s['title'] and len(norm(r['title']))>=12 and norm(r['title'])==norm(s['title']) and r['year'] and r['year']==s['year']:why='题名+年份'
  elif set(filter(None,r['sha']))&set(filter(None,s['sha'])):why='sha256'
  if why:merge(i,j,why)
groups=collections.defaultdict(list)
for i,r in enumerate(rows):groups[root(i)].append(r)
topics={
 '非平稳风与雷暴风':r'nonstation|non.synoptic|downburst|thunderstorm|gust.front|transient wind|hurricane|typhoon|tornado|extreme wind|wavelet|non.station|tropical cyclone|tropical storm|burst',
 '阵风因子与峰值因子':r'gust factor|peak factor|gust effect|gust response|gust.front factor|wind speed averaging|averaging interval|gust loading|wind load effects',
 '高层建筑气动与风振':r'tall building|high.rise|building|aeroelastic|wind.excit|wind.induc|damping|slosh|tuned mass|motion|vortex|interference|buffeting|structural modal|isolated roughened|pressure and force|full.scale and model',
 '随机过程模拟与非高斯':r'random|stochastic|non.gaussian|non.normal|simulation|spectral|spectrum|spectra|arma|quadratic|probabilistic|coherence|cross.correlation|turbulence',
 '数据驱动与机器学习':r'machine learning|data.driven|database|digital twin|neural|knowledge.based|surrogate|deep learning|artificial intelligence',
 '桥梁气动与颤振':r'bridge|flutter|cable|suspension span',
 '可靠度与性能化设计':r'reliab|performance.based|risk|hazard|uncertainty|optimization|design wind|codif|load combination|fragility|failure|safety',
 '风浪/海洋结构':r'wave|ocean|offshore|marine|tension.leg|surge|sea surface|platform|hydrodynamic',
 '计算风工程与数值模型':r'computational fluid|\bcfd\b|large.eddy|numerical simulation|computational wind|wind tunnel|fluid.structure|mesoscale|microscale|numerical models|boundary layer model',
 '结构控制与状态识别':r'control|absorber|damper|hybrid system|system identification|virtual dynamic shaker|morphing|actuation|beat phenomenon|structural form',
 '风荷载与试验方法':r'wind load|wind force|wind engineering|dynamic load|pressure|model data|structural design|wind effects|wind.turbine|aerodynamic response',
 '信号处理与数值方法':r'interpolation|time.frequency|signal analysis|discrete.time|statistical cubicization|nonlinear|predictive model',
 '教学讲稿与非论文材料':r'microsoft powerpoint|presentation|intro wind|topics in the wind|living laboratory|crowdsourcing|the question describing',
 '风工程综合/其他待细分':r'.',
}
records=[]
for group in groups.values():
 group.sort(key=lambda r:('Zotero','EndNote','Desktop').index(r['lib']))
 best=next((r for r in group if r['title'] and '题名仅' not in r['note']),group[0])
 title=best['title']; yy=best['year']; found=[k for k,p in topics.items() if k!='风工程综合/其他待细分' and re.search(p,title,re.I)]
 if not found: found=['风工程综合/其他待细分']
 ids=[]
 for r in group:
  ids.extend([r['id']]+([r['extra']] if r.get('extra') else []))
 ids=list(dict.fromkeys(x for x in ids if x))
 notes=list(dict.fromkeys(r['note'] for r in group if r['note']))
 if len(group)>1: notes.append('合并依据 '+','.join(sorted(reason[root(rows.index(group[0]))])) if reason[root(rows.index(group[0]))] else '合并依据待核')
 authors=best['authors']; pos=kpos(authors)
 records.append(dict(work_id='',title=title,year=yy,venue=best['venue'] or next((r['venue'] for r in group if r['venue']),''),authors='; '.join(authors)+(f' [Kareem 第{pos}作者]' if pos else ' [作者序待核]'),doi=next((r['doi'] for r in group if r['doi']),''),library_item_ids=';'.join(ids),libraries=';'.join(dict.fromkeys(r['lib'] for r in group)),has_fulltext='是' if any(r['has'] for r in group) else '否',pdf_pages=max((r['pages'] for r in group),default=0) or '',topic=';'.join(found),dedup_note='; '.join(notes),_n=len(group)))
records.sort(key=lambda r:(r['year'],norm(r['title']),r['library_item_ids']))
for n,r in enumerate(records,1):r['work_id']=f'KRM-{n:04d}'
with open(OUT/'inventory.csv','w',newline='',encoding='utf-8-sig') as f:
 cols=['work_id','title','year','venue','authors','doi','library_item_ids','libraries','has_fulltext','pdf_pages','topic','dedup_note']; w=csv.DictWriter(f,cols);w.writeheader();w.writerows({k:r[k] for k in cols} for r in records)
print('raw',len(rows),collections.Counter(r['lib'] for r in rows),'works',len(records),'merge',len(rows)-len(records),'coverage main',sum('风工程综合/其他待细分' not in r['topic'] for r in records))
# OpenAlex directory: author identity verified by ID; filter to signed works, not thematic matches alone.
works=[]
for page in range(1,8):
 url=f'https://api.openalex.org/works?filter=authorships.author.id:A5069470138&per-page=100&page={page}&select=id,title,publication_year,doi,cited_by_count,primary_location,best_oa_location,authorships,type'
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'FirstLab/1.0 (bibliographic inventory)'}),timeout=25) as resp: result=json.load(resp)
 except Exception as ex: print('openalex failure',page,repr(ex));break
 works.extend(result['results']);print('openalex page',page,len(result['results']))
 if len(result['results'])<100:break
 time.sleep(.2)
(OUT/'openalex_directory.json').write_text(json.dumps(works,ensure_ascii=False,indent=1),encoding='utf-8')
localdoi={r['doi'] for r in records if r['doi']}; localtitle={norm(r['title']) for r in records if r['title']}
missing=[]
for w in works:
 title=w.get('title') or ''; d=doi(w.get('doi')); y=w.get('publication_year')
 if not d or not y or not title or d in localdoi or norm(title) in localtitle:continue
 # Low-confidence desktop titles can be truncated; do not assert such a candidate is absent.
 if any(len(t)>=22 and norm(title).startswith(t) for t in localtitle):continue
 if not any('kareem' in (a.get('author',{}).get('display_name') or '').lower() for a in w.get('authorships',[])):continue
 pl=w.get('primary_location') or {}; venue=(pl.get('source') or {}).get('display_name') or ''
 if w.get('type') not in ('article','review','proceedings-article','book-chapter') or not venue:continue
 missing.append(dict(title=title,year=y,venue=venue,doi=d,cites=w.get('cited_by_count') or 0,oa='是' if (w.get('best_oa_location') or {}).get('pdf_url') else ('目录标 OA，PDF 未核' if pl.get('is_oa') else '未见 OA'),url=w['id']))
missing.sort(key=lambda x:(-x['cites'],x['year']))
with open(OUT/'gaps.md','w',encoding='utf-8') as f:
 f.write('# Kareem 代表作待补目录（仅题录，不下载）\n\n来源：[OpenAlex 作者目录](https://openalex.org/A5069470138)，查询 `authorships.author.id:A5069470138`，本次逐页取得 '+str(len(works))+' 条；按 DOI 或标准化题名排除已入库，按被引数排序。被引数为 OpenAlex 查询时值，不代表学术价值；“未见 OA”不是断言不可获取。此表的“缺”限当前三库元数据检出的范围，尤其远端低置信度题名可能漏配，补库前请 DOI 回核。\n\n| 题名 | 年 | 期刊/会议 | DOI | 代表性依据 | 开放获取 | 目录 |\n|---|---:|---|---|---|---|---|\n')
 for x in missing[:25]:f.write('| '+ ' | '.join(str(x[k]).replace('|','/') for k in ('title','year','venue','doi'))+' | OpenAlex 被引 '+str(x['cites'])+' | '+x['oa']+' | '+x['url']+' |\n')
 f.write('\n筛选说明：仅作品目录，未查阅或下载 PDF；发表类型限 article/review/proceedings-article/book-chapter；DOI 必填，排除库内同 DOI、相同归一化题名，或库内 ≥22 字符题名为其前缀者（防止截断标题误报）。逐条作者名单含 Kareem。索引可能存在同名/版本漏配，须补库前再次核对 DOI 和本人署名。\n')
count=collections.Counter(); years=collections.defaultdict(list); exemplars=collections.defaultdict(list)
for r in records:
 for t in r['topic'].split(';'):
  count[t]+=1
  if r['year']:years[t].append(int(r['year']))
  exemplars[t].append(r)
with open(OUT/'topic_map.md','w',encoding='utf-8') as f:
 f.write('# Kareem 库内主题图\n\n主题为题名关键词的多标签初分，并非读全文后学术判断；同篇可计入多个组，组篇数不可相加。来源：本地 Zotero 原始父条目、EndNote/台式机元数据、ftkb 附件表，见 README。\n\n')
 for t in topics:
  if not count[t]:continue
  ys=years[t]
  f.write(f'## {t}（{count[t]} 篇，{min(ys) if ys else "未知"}–{max(ys) if ys else "未知"}）\n\n')
  candidates=sorted(exemplars[t],key=lambda r:(bool(re.search(r'review|perspective|state.of.the.art|advances|overview|framework|codif|simulation|modeling|analysis',r['title'],re.I)),bool(r['doi']),int(r['year'] or 0)),reverse=True)
  for r in candidates[:5]:f.write(f'- {r["title"]} ({r["year"] or "年不详"}; {r["work_id"]}; DOI {r["doi"] or "未录"})\n')
  f.write('\n')
 f.write(f'主题标签覆盖：{sum(bool(r["topic"]) for r in records)}/{len(records)} = {sum(bool(r["topic"]) for r in records)/len(records):.1%}；具体主题（不计“其他待细分”）：{sum("风工程综合/其他待细分" not in r["topic"] for r in records)}/{len(records)} = {sum("风工程综合/其他待细分" not in r["topic"] for r in records)/len(records):.1%}。其他待细分 {count["风工程综合/其他待细分"]} 篇，不能用“其他”虚增实质覆盖率。\n')
with open(OUT/'README.md','w',encoding='utf-8') as f:
 f.write('# L22.5-01 阶段一方法与审计\n\n')
 f.write('查询：Zotero 只读 SQLite 对 `items + itemCreators + creators + itemData` 的 Kareem 姓名变体做父条目枚举；EndNote `endnote_records_v3.csv` 作者字段及 ftKB `attachments` 作者补录；台式机 `desktop_records_v3.csv` 作者及 ftKB 条目；网络仅 OpenAlex `authors?search=Ahsan Kareem` 定位作者 ID A5069470138，再 `works?filter=authorships.author.id:A5069470138` 逐页查题录（只传 DOI/公开目录，不传 PDF 片段）。来源原件只读，输出仅本目录。\n\n')
 f.write('原始候选 '+str(len(rows))+' 条：'+', '.join(f'{k} {v}' for k,v in collections.Counter(r['lib'] for r in rows).items())+'；去重后 '+str(len(records))+' 件，合并减少 '+str(len(rows)-len(records))+' 条。索引中仅有 PDF 的 Kareem 作者条目 '+str(len(aidx))+'（按库 '+str(dict(collections.Counter(r['library'] for r in aidx)))+'），不等于 Zotero 父条目数。\n\n')
 f.write('去重只按同 DOI、完整归一化题名+同年或同文件 SHA-256，已知 DOI 冲突不并；同名/不同年、作者缺失、台式机低置信度标题均保留待核。work_id 是本次排序内临时号，不是外部永久标识。PDF 页数优先来自 ftKB 索引或原远端清单；Zotero 是否全文按本地路径存在、EndNote 按清单路径/ftKB 索引、Desktop 表示远端 I 盘有文件但本机未核验。无索引的 Zotero PDF 页数空白，不代表 0 页。Desktop 的 PPT 导出可作为署名作品候选，但不等同期刊论文。\n\n')
 f.write(f'主题全部有标签 {len(records)}/{len(records)}；具体主题覆盖 {sum("风工程综合/其他待细分" not in r["topic"] for r in records)}/{len(records)}。分组仅题名规则，抽代表作前须逐篇核原文和作者顺序。OpenAlex 返回 {len(works)} 条（原始目录快照 openalex_directory.json）；缺口建议 {min(25,len(missing))} 条。\n\n')
 f.write('问题：ftKB 附件作者常缩为姓氏，Zotero 作者顺序取父条目；EndNote 和 Desktop 解析作者格式不统一，个别 “Kareem” 只是含于完整作者字符串，需抽查。Desktop 题名若来自文件名或 PDF 首页候选而非书目仍可能错。分主题如“其他待细分”未达 10% 前不能声称实质覆盖达标。\n')
