#!/usr/bin/env python3
"""Read-only reconciliation of frozen OpenAlex snapshot against frozen local inventory.
Writes only corpus_status.csv, corpus_status_extra.csv, corpus_summary.md,
oa_to_fetch.csv beside this script. No downloads or external API calls.
"""
import csv, json, re, unicodedata, collections
from pathlib import Path
P=Path(__file__).resolve().parent
OA=json.loads((P/'openalex_directory.json').read_text(encoding='utf-8'))
with (P/'inventory.csv').open(encoding='utf-8-sig',newline='') as f: LOCAL=list(csv.DictReader(f))
def n(s): return re.sub(r'[^a-z0-9]+','',unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower())
def d(s): return re.sub(r'^https?://(?:dx\.)?doi\.org/','',(s or '').strip().lower()).strip(' .')
def year(x): return str(x or '').strip()
def typ(x):
    return {'conference-paper':'proceedings','preprint':'其他:preprint','editorial':'其他:editorial','peer-review':'其他:peer-review'}.get(x,x if x in ('article','review','book-chapter') else '其他:'+str(x))
def url(x):
    best=x.get('best_oa_location') or {}
    loc=x.get('primary_location') or {}
    candidates=[best,loc]
    for a in candidates:
        if a.get('is_oa') and a.get('pdf_url'): return a['pdf_url'],'OA-PDF（目录标记，未下载）'
    for a in candidates:
        if a.get('is_oa') and a.get('landing_page_url'): return a['landing_page_url'],'OA-落地页（目录标记，未验证可下载）'
    # OpenAlex best OA location sometimes omits is_oa but has a valid location
    if best.get('pdf_url'): return best['pdf_url'],'OA-PDF（best_oa_location，未下载）'
    if best.get('landing_page_url'): return best['landing_page_url'],'OA-落地页（best_oa_location，未验证可下载）'
    return '', '目录未给 OA 链接（不等于无 OA）'
def csvwrite(name,rows,keys):
    with (P/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:r.get(k,'') for k in keys} for r in rows)
LD=collections.defaultdict(list);LT=collections.defaultdict(list)
for r in LOCAL:
    if d(r['doi']): LD[d(r['doi'])].append(r)
    if n(r['title']) and year(r['year']): LT[n(r['title']),year(r['year'])].append(r)
# Confirm same exact DOI/title-year really constitutes a single work, otherwise leave unresolved.
def local_match(x):
    nd=d(x.get('doi')); nt=n(x.get('title')); y=year(x.get('publication_year'))
    bydoi=LD.get(nd,[]) if nd else []
    bytitle=LT.get((nt,y),[]) if nt and y else []
    if bydoi:
        ids={r['work_id'] for r in bydoi}; t_ids={r['work_id'] for r in bytitle}
        if len(ids)!=1 or (t_ids and ids != t_ids): return None,'候选冲突：同 DOI 对应多个本地号/题名+年指向另一号'
        return bydoi[0],'DOI'
    if bytitle:
        clean=[r for r in bytitle if not nd or not d(r['doi']) or nd==d(r['doi'])]
        if len(clean)==1 and len(bytitle)==1: return clean[0],'题名+年'
        return None,'候选冲突：题名+年相同但 DOI 冲突或对应多个号'
    return None,''
# OA exact title-year duplicate; do not collapse different nonempty DOI.
bytitle=collections.defaultdict(list)
for x in OA:
    if n(x.get('title')) and year(x.get('publication_year')):bytitle[n(x['title']),year(x['publication_year'])].append(x)
parent={x['id']:x['id'] for x in OA}
def root(v):
    while parent[v]!=v:
        parent[v]=parent[parent[v]];v=parent[v]
    return v
def union(a,b):
    a,b=root(a),root(b)
    if a!=b:parent[max(a,b)]=min(a,b)
for vals in bytitle.values():
    for i,x in enumerate(vals):
        for z in vals[i+1:]:
            if not d(x.get('doi')) or not d(z.get('doi')) or d(x['doi'])==d(z['doi']): union(x['id'],z['id'])
# Preprint/formal versions: do NOT guess by approximate titles; exact normalized title
# in adjacent years, same author and no conflicting DOI is an explicit weak candidate.
# Preserve them separate and disclose residual version duplication in summary.
canonical={}
for x in OA:
    rt=root(x['id']); old=canonical.get(rt)
    # preferentially retain a DOI and a published non-preprint entry
    if old is None or (bool(d(x.get('doi'))),x.get('type') not in ('preprint','editorial'),x.get('cited_by_count') or 0)>(bool(d(old.get('doi'))),old.get('type') not in ('preprint','editorial'),old.get('cited_by_count') or 0): canonical[rt]=x
rows=[]
for x in OA:
    m,basis=local_match(x); o,os=url(x); dup=canonical[root(x['id'])]['id'] if canonical[root(x['id'])]['id']!=x['id'] else ''
    status='库内有全文' if m and m['has_fulltext']=='是' else ('库内只有题录' if m else '不在库')
    note=[]
    if basis.startswith('候选冲突'): note.append(basis+'；暂列不在库待人工核对')
    if m and m['unpublished']=='是':note.append('本地被标 unpublished，非正式论文身份需核')
    if m and ('Desktop' in m['libraries'] or '远端' in m['dedup_note']):note.append('台式机远端文件未在本机核验可读性')
    if m and 'KRM-0186'==m['work_id']:note.append('本地为编辑署名章节，非本章作者；归属须复核')
    if dup:note.append('目录重复：与 canonical 题名+年相同且 DOI 不冲突；不计独立作品')
    rows.append(dict(openalex_id=x['id'],title=x.get('title') or '',year=year(x.get('publication_year')),venue=((x.get('primary_location') or {}).get('source') or {}).get('display_name') or '',doi=d(x.get('doi')),type=typ(x.get('type')),cited_by=x.get('cited_by_count') or 0,status=status,work_id=m['work_id'] if m else '',match_basis=basis if m else '',oa_status=os,oa_url=o,duplicate_of=dup,note='；'.join(note)))
csvwrite('corpus_status.csv',rows,['openalex_id','title','year','venue','doi','type','cited_by','status','work_id','match_basis','oa_status','oa_url','duplicate_of','note'])
# Local works not matched by any OA record; keep unpublished and non-author items explicitly separated.
matched={r['work_id'] for r in rows if r['work_id']}
extra=[]
for r in LOCAL:
    if r['work_id'] in matched:continue
    extra.append(dict(work_id=r['work_id'],title=r['title'],year=r['year'],venue=r['venue'],doi=r['doi'],libraries=r['libraries'],library_item_ids=r['library_item_ids'],has_fulltext=r['has_fulltext'],unpublished=r['unpublished'],topic=r['topic'],note=r['dedup_note']))
csvwrite('corpus_status_extra.csv',extra,['work_id','title','year','venue','doi','libraries','library_item_ids','has_fulltext','unpublished','topic','note'])
unique=[r for r in rows if not r['duplicate_of']]
missing=[r for r in unique if r['status']=='不在库']
fetch=[r for r in missing if r['oa_url']]
csvwrite('oa_to_fetch.csv',fetch,['title','year','doi','oa_url','openalex_id','oa_status'])
# Topic mapping: carry local labels where possible; otherwise deterministic title regex.
# Never mistake 'wavelet' for ocean waves; group order lets more precise labels coexist.
topics={
'非平稳风与雷暴风':r'non[ -]?station|non[ -]?synoptic|downburst|thunderstorm|gust[ -]?front|transient wind|hurricane|typhoon|tornado|tropical cyclone|tropical storm',
'阵风因子与峰值因子':r'gust factor|peak factor|gust effect|gust response|gust.front factor|wind speed averaging|averaging interval|gust loading',
'高层建筑气动与风振':r'tall building|high[ -]?rise|building|aeroelastic|wind[ -]?excit|wind[ -]?induc|damping|slosh|tuned mass|motion|vortex|interference|buffeting',
'随机过程模拟与非高斯':r'random|stochastic|non[ -]?gaussian|non[ -]?normal|simulation|spectral|spectrum|spectra|arma|quadratic|probabilistic|coherence|correlation|turbulence',
'数据驱动与机器学习':r'machine learning|data[ -]?driven|database|digital twin|neural|knowledge[ -]?based|surrogate|deep learning|artificial intelligence',
'桥梁气动与颤振':r'bridge|flutter|cable|suspension span',
'可靠度与性能化设计':r'reliab|performance[ -]?based|risk|hazard|uncertainty|optim|design wind|codif|load combination|fragility|failure|safety',
'风浪/海洋结构':r'\bwave(?:s)?\b|ocean|offshore|marine|tension[ -]?leg|\bsurge\b|sea surface|platform|hydrodynamic',
'计算风工程与数值模型':r'computational fluid|\bcfd\b|large[ -]?eddy|numerical simulation|computational wind|wind tunnel|fluid[ -]?structure|mesoscale|microscale|numerical models|boundary layer model',
'结构控制与状态识别':r'control|absorber|damper|hybrid system|system identification|virtual dynamic shaker|morphing|actuation',
'风荷载与试验方法':r'wind load|wind force|wind engineering|dynamic load|pressure|model data|structural design|wind effects|wind[ -]?turbine|aerodynamic response',
'信号处理与数值方法':r'interpolation|time[ -]?frequency|signal analysis|discrete[ -]?time|statistical cubicization|nonlinear|predictive model',
'教学讲稿与非论文材料':r'microsoft powerpoint|presentation|intro wind|topics in the wind|living laboratory|crowdsourcing|the question describing',
}
localid={r['work_id']:r for r in LOCAL}
def labels(r):
    if r['work_id']:
        return [a for a in localid[r['work_id']]['topic'].split(';') if a in topics or a=='风工程综合/其他待细分']
    found=[k for k,v in topics.items() if re.search(v,r['title'],re.I)]
    return found or ['风工程综合/其他待细分']
def dec(y):
    if not y or not y.isdigit():return '年不详'
    return str(int(y)//10*10)+'s'
status_names=['库内有全文','库内只有题录','不在库']
C=collections.Counter(r['status'] for r in unique)
bydec=collections.defaultdict(lambda:collections.Counter())
bytopic=collections.defaultdict(lambda:collections.Counter())
for r in unique:
    bydec[dec(r['year'])][r['status']]+=1
    for t in labels(r):bytopic[t][r['status']]+=1
nooa=sorted([r for r in missing if not r['oa_url']],key=lambda r:-int(r['cited_by']))[:30]
conflicts=[r for r in rows if '候选冲突' in r['note']]
# OA records which match a single local work multiple times are potential OpenAlex version duplicates.
amb=collections.defaultdict(list)
for r in unique:
    if r['work_id']:amb[r['work_id']].append(r['openalex_id'])
amb={k:v for k,v in amb.items() if len(v)>1}
def esc(x):return str(x or '').replace('|','/').replace('\n',' ')
def row_table(keys): return '| '+' | '.join(map(esc,keys))+' |\n'+'|'+'|'.join('---' for _ in keys)+'|\n'
with (P/'corpus_summary.md').open('w',encoding='utf-8') as f:
    f.write('# Kareem 公开目录与本地库对照（第一轮）\n\n')
    f.write('数据源：本地冻结的 [OpenAlex 作者 A5069470138 目录](https://openalex.org/A5069470138) `openalex_directory.json`（511 条）、本地 `inventory.csv`（201 件，Zotero/EndNote/台式机及 ftKB 前期只读汇总）；生成脚本 `build_corpus_status.py`。本轮不下载全文、不向外传原文。OpenAlex 是作者归属的目录候选，不等于所有作品的真实全集。\n\n')
    f.write(f'目录原始 {len(rows)} 条，确定性同题同年且 DOI 不冲突的重复 {sum(bool(r["duplicate_of"]) for r in rows)} 条，目录去重 {len(unique)} 件；额外本地未匹配 {len(extra)} 件。目录与本地不重合合计 {len(unique)+len(extra)} 件候选作品，**不是经逐篇首页验证的真实作品总数**；其中本地额外 unpublished {sum(r["unpublished"]=="是" for r in extra)} 件。若只计目录和本地已标已发表的额外候选，合计 {len(unique)+sum(r["unpublished"]!="是" for r in extra)} 件（仍有版本/编辑误署风险）。\n\n')
    f.write(f'目录去重后的状态：全文标记 {C[status_names[0]]}/{len(unique)}（{C[status_names[0]]/len(unique):.1%}），只有题录 {C[status_names[1]]}/{len(unique)}（{C[status_names[1]]/len(unique):.1%}），不在库 {C[status_names[2]]}/{len(unique)}（{C[status_names[2]]/len(unique):.1%}）。题录覆盖（前两项） {(C[status_names[0]]+C[status_names[1]])/len(unique):.1%}。本地全文标记不等于本机可打开：Desktop I 盘未核验，EndNote/ftKB 索引可能陈旧。\n\n')
    f.write(f'目录缺口中给 OA 链接 {len(fetch)}/{len(missing)} 件（仅 OpenAlex 目录标记，待 litwiki 核许可证、作者和下载可得性）；无链接 {len(missing)-len(fetch)} 件不等于付费墙。去重后目录与本地同一 work_id 对上多个 OA ID 的候选组 {len(amb)} 个，尚未硬合并；标题近似或跨年预印本亦未硬合并，因此“真实作品”数字是保守待审上界。\n\n')
    f.write('## 按年代：目录去重作品数及缺口\n\n'+row_table(['年代','全文','只有题录','不在库','合计']))
    for k in sorted(bydec):
        c=bydec[k];f.write('| '+ ' | '.join([k]+[str(c[s]) for s in status_names]+[str(sum(c.values()))])+' |\n')
    f.write('\n## 按 13 个主题：目录去重作品数及缺口\n\n标题关键词粗分、多标签；已匹配项沿用 inventory 的标签，未匹配项由脚本规则归类，组间不能求和，“其他待细分”不能当作实质主题。\n\n'+row_table(['主题','全文','只有题录','不在库','合计']))
    for k in [*topics,'风工程综合/其他待细分']:
        c=bytopic[k];f.write('| '+ ' | '.join([k]+[str(c[s]) for s in status_names]+[str(sum(c.values()))])+' |\n')
    f.write('\n## 无 OA 目录链接、按 OpenAlex 被引数排序的前 30 个缺口\n\n“无 OA”仅指此快照没给链接；引用次数为目录快照，不是代表性/质量认证。\n\n'+row_table(['序','标题','年','DOI','被引','OpenAlex']))
    for i,r in enumerate(nooa,1):f.write('| '+' | '.join(map(esc,[i,r['title'],r['year'],r['doi'],r['cited_by'],r['openalex_id']]))+' |\n')
    f.write('\n## 匹配、去重与待核问题\n\n')
    f.write('OpenAlex DOI 去前缀并小写、标题 Unicode 归一化并移除非字母数字；优先 DOI 精确匹配库内 work_id，其次完整标题+同年（有不同 DOI 时不匹配）；不按相似题名硬配。仅完整归一化标题+同年且 DOI 不冲突的 OpenAlex 条目标 duplicate_of；跨年预印本、相似短标题、不同 DOI 均留在目录内。目录与本地额外名单不可凭标题关键词作身份认定。\n\n')
    f.write(f'本轮自动匹配冲突 {len(conflicts)} 条，见 corpus_status.csv note；同一个本地号对上多个独立 OA 条目 {len(amb)} 组，下面列出待核：\n\n')
    for k,ids in list(amb.items())[:40]:f.write(f'- {k}: '+', '.join(ids)+'\n')
    if not amb:f.write('- 无。\n')
    f.write('本地未匹配项见 corpus_status_extra.csv：可能是真正目录外的会议/报告，也可能是题名或 DOI 缺漏导致漏配；其中课程幻灯为 unpublished，KRM-0186 为章节编辑并非该章节作者。第三 EndNote 库尚未给出，此轮覆盖率必须在补库后重算。\n')
print('OA raw',len(rows),'dedup',len(unique),'duplicates',len(rows)-len(unique),'local',len(LOCAL),'extra',len(extra),'status',dict(C),'OA missing',len(fetch),'conflicts',len(conflicts),'multi-ID groups',len(amb))
