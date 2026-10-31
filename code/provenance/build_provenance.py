#!/usr/bin/env python3
"""Local metadata-only provenance audit; no network/PDF access."""
import csv, json, re, collections
from pathlib import Path
P=Path(__file__).resolve().parents[1]; O=Path(__file__).resolve().parent

def readcsv(n):
    with (P/n).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def outcsv(n, rows, fields):
    with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def yr(s):
    m=re.search(r'\b(19\d\d|20\d\d)\b',str(s or ''));return int(m.group()) if m else None
def decade(y):
    return '≤1999' if y and y<=1999 else '2000–2009' if y and y<=2009 else '2010–2019' if y and y<=2019 else '≥2020' if y and y>=2020 else '不详'
def review(title,typ=''):
    return '是' if re.search(r'\b(review|revisit(?:ing|ed)?|perspective|overview|frontiers?|state[ -]of[ -]the[ -]art|lessons?|keynote|invited|codification)\b|综述|展望|回顾|前沿|重新审视|述评',title or '',re.I) or typ=='review' else '否'
def conference(title,venue,typ):
    return '是' if typ in ('proceedings','proceedings-article') or re.search(r'conference|congress|symposium|workshop|proceedings|会议|大会|论坛', (venue or '')+' '+(title or ''),re.I) else '否'
def tier(y,pos):
    if not y or pos=='不详':return '未知'
    if y<=2009:return 'T1' if pos in ('单作者','第一作者') else 'T2'
    return 'T2' if pos in ('单作者','第一作者') else 'T3'
FIELDS=['work_id','openalex_id','title','year','decade','kareem_position','n_authors','tier','invited_review','conference','has_fulltext','判层依据','venue','type','topic','source','status']
raw=json.loads((P/'openalex_directory.json').read_text(encoding='utf-8'))
byoa={x['id']:x for x in raw}; stat=readcsv('corpus_status_r4.csv'); inv=readcsv('inventory.csv'); byid={x['work_id']:x for x in inv}; extra=readcsv('corpus_status_extra_r2.csv'); thesis=readcsv('theses/theses_in_library.csv'); jud=readcsv('judgments_raw.csv')
assert len(stat)==511 and len(inv)==201 and len(extra)==75
records=[]; exclusions=collections.Counter(); anomalies=[]
for s in stat:
    if s['status'] in ('non_paper','not_kareem') or s['duplicate_of']:
        exclusions['duplicate' if s['duplicate_of'] else s['status']]+=1;continue
    a=byoa[s['openalex_id']]; authors=a.get('authorships') or []
    ka=[(i,z) for i,z in enumerate(authors) if (z.get('author') or {}).get('id') and ((z.get('author') or {}).get('id') or '').rstrip('/').endswith('/A5069470138')]
    if len(ka)==1:
        i,k=ka[0];corr=k.get('is_corresponding') is True
        pos='单作者' if len(authors)==1 else '第一作者' if i==0 else '末位或通讯' if i==len(authors)-1 or corr else '中间'
        basis=f"OpenAlex authorships: A5069470138 第{i+1}/{len(authors)}作者; is_corresponding={k.get('is_corresponding')}; 年份={s['year']}; r4状态={s['status']}"
    else:
        pos='不详';basis=f"OpenAlex authorships 未唯一确认 A5069470138 (匹配数 {len(ka)})；不可凭目录归属推断作者位置；r4状态={s['status']}";anomalies.append(s['openalex_id'])
    y=yr(s['year']);iv=byid.get(s['work_id'],{})
    records.append(dict(work_id=s['work_id'],openalex_id=s['openalex_id'],title=s['title'],year=s['year'],decade=decade(y),kareem_position=pos,n_authors=str(len(authors)) if authors else '',tier=tier(y,pos),invited_review=review(s['title'],a.get('type','')),conference=conference(s['title'],s['venue'],s['type']),has_fulltext='是' if s['status']=='库内有全文' else '否',判层依据=basis,venue=s['venue'],type=s['type'],topic=iv.get('topic',''),source='OpenAlex+r4',status=s['status']))
# Extra works are exactly inventory minus matched IDs, not 75 arbitrary metadata lines.
matched={r['work_id'] for r in records if r['work_id']}
extras=[i for i in inv if i['work_id'] not in matched]
assert len(extras)==75 and {x['work_id'] for x in extras}=={x['work_id'] for x in extra}
for i in extras:
    text=i['authors'] or '';m=re.search(r'Kareem 第(\d+)作者',text); names=[z.strip() for z in re.split(r';|\band\b',re.sub(r'\s*\[Kareem 第\d+作者\]','',text),flags=re.I) if z.strip()]
    n=len(names) if names else None; idx=int(m.group(1)) if m else None
    # Avoid treating a truncated author list as complete: use the position but unknown total unless consistent.
    if n and idx and idx<=n and sum(bool(re.search(r'\bkareem\b',x,re.I)) for x in names)==1:
        pos='单作者' if n==1 else '第一作者' if idx==1 else '末位或通讯' if idx==n else '中间'
        basis=f"inventory authors 字段：Kareem 第{idx}/{n}作者；非 OpenAlex 校核；未标通讯作者；年份={i['year'] or '缺失'}"
    else:
        pos='不详';basis=f"inventory authors={text!r}，作者总数/位置不可可靠解析；年份={i['year'] or '缺失'}";n=None
    y=yr(i['year']);is_thesis=bool(re.search(r'thesis|dissertation|学位论文',i['title']+' '+i['venue'],re.I))
    t='T1' if is_thesis and i['work_id']=='KRM-0025' else 'T0' if is_thesis else tier(y,pos)
    if is_thesis:basis+='；学位论文单列：本人博士 T1，其他学位题录未确认为本人博士/学生指导'
    if i['work_id']=='KRM-0186':
        pos='不详';t='未知';basis+='；前轮人工备注：Kareem 是卷编辑而非本章作者，不归为其署名论文；仅保留库存账目行'
    records.append(dict(work_id=i['work_id'],openalex_id='',title=i['title'],year=i['year'],decade=decade(y),kareem_position=pos,n_authors=str(n or ''),tier=t,invited_review=review(i['title']),conference=conference(i['title'],i['venue'],''),has_fulltext=i['has_fulltext'],判层依据=basis,venue=i['venue'],type='thesis' if is_thesis else '',topic=i['topic'],source='inventory extra',status='库内目录外'))
# Include theses referenced by the thesis audit, distinguish own thesis from student-authored thesis.
known={r['work_id'] for r in records if r['work_id']}
for i in thesis:
    m=re.search(r'KRM-\d+',i['library_where']);wid=m.group() if m else ''
    if wid in known:
        r=next(r for r in records if r['work_id']==wid)
        if i['student']=='Ahsan Kareem':
            r['tier']='T1' if i['confidence']=='已证实' and 'Ph.D.' in i['degree'] else 'T0'
            r['type']='thesis';r['conference']='否'
            r['判层依据']+='；theses_in_library: '+i['degree']+' '+i['confidence']
        continue
    # Student theses concern the author as adviser; not a Kareem coauthored paper.
    key='TH-'+str(len([r for r in records if r['source']=='theses_in_library'])+1).zfill(3)
    records.append(dict(work_id=key,openalex_id='',title=i['title'],year=i['year'],decade=decade(yr(i['year'])),kareem_position='非署名（导师）' if i['confidence']=='已证实' else '不详',n_authors='1',tier='T3' if i['confidence']=='已证实' else 'T0',invited_review='否',conference='否',has_fulltext=i['has_fulltext'],判层依据=f"theses_in_library: {i['student']} {i['degree']}；Kareem角色={i['kareem_role']}；{i['confidence']}；证据PDF物理页={i['evidence_page'] or '无'}；学生论文 T3 仅限证实指导；其余 T0 待核；并非 Kareem 署名论文",venue=i['university'],type='thesis',topic='',source='theses_in_library',status='库内目录外'))
outcsv('corpus_provenance.csv',records,FIELDS)
# KC mapping: restrict formal entries to before appendix.
text=(P/'Kareem_判断清单_v1.1.md').read_text(encoding='utf-8'); formal=re.split(r'\n##?\s*附录',text,maxsplit=1)[0]
blocks=re.findall(r'(?ms)^###\s+(KC-\d+)\s*[｜|].*?(?=^###\s+KC-|\Z)',formal)
sections=re.split(r'(?=^###\s+KC-\d+\s*[｜|])',formal,flags=re.M)
byj={x['judgment_id']:x for x in jud};bywork=collections.defaultdict(list)
for r in records:
    if r['work_id']:bywork[r['work_id']].append(r)
kcs=[]; link=[]
for block in sections:
    m=re.match(r'###\s+(KC-\d+)\s*[｜|]',block)
    if not m:continue
    kc=m.group(1);line=next((z for z in block.splitlines() if z.startswith('出处：')),'');ids=list(dict.fromkeys(re.findall(r'KJ-\d+',line)))
    if not ids:raise ValueError('no sources '+kc)
    sources=[]
    for jid in ids:
        j=byj[jid];opts=bywork[j['work_id']]
        if len(opts)!=1:raise ValueError(f'KC={kc} {jid} {j["work_id"]} mappings={len(opts)}')
        r=opts[0];sources.append(r);link.append(dict(kc=kc,judgment_id=jid,work_id=j['work_id'],title=r['title'],year=r['year'],openalex_id=r['openalex_id'],tier=r['tier'],kareem_position=r['kareem_position'],round=j['round'],pdf_page=j['pdf_page']))
    ranks={'T1':3,'T2':2,'T3':1,'未知':0};best=max(sources,key=lambda z:ranks[z['tier']])['tier']
    kcs.append(dict(kc=kc,judgment_ids=';'.join(ids),work_ids=';'.join(dict.fromkeys(j['work_id'] for j in (byj[x] for x in ids))),source_tiers=';'.join(r['tier'] for r in sources),best_tier=best,only_T3='是' if all(r['tier']=='T3' for r in sources) else '否',note='最高层指元数据代理而非原作者归属；未知不等于 T3'))
assert len(kcs)==57,(len(kcs),[x['kc'] for x in kcs]);assert len({x['kc'] for x in kcs})==57
outcsv('kc_provenance.csv',kcs,['kc','judgment_ids','work_ids','source_tiers','best_tier','only_T3','note'])
outcsv('kc_source_links.csv',link,['kc','judgment_id','work_id','title','year','openalex_id','tier','kareem_position','round','pdf_page'])
# Questions: topic/keyword relevance is a shortlisting heuristic, not literature proof.
proj=Path(__file__).resolve().parents[3]/'05_Projects/Kareem_Expertise.md'
qtext=proj.read_text(encoding='utf-8');qs=[]
for line in qtext.splitlines():
    m=re.match(r'\|\s*(Q-[\w-]+)(?:（[^）]+）)?\s*\|[^|]*\|\s*([^|]+)\|',line)
    if m:qs.append((m.group(1),m.group(2).strip()))
assert len(qs)==8,qs
patterns={
 'Q-DWT-1':[r'peak factor|non.gaus|hermite|extreme|pressure|short.record',r'峰值|非高斯|风压'],
 'Q-DWT-2':[r'nonstationary|non.stationary|time.varying|averaging|wavelet|mean wind',r'非平稳|时变'],
 'Q-WX-1':[r'gust.front|downburst|thunderstorm|gust.factor|gust.averaging|peak gust',r'阵风|雷暴|下击暴流'],
 'Q-WX-2':[r'gust.factor|gust.averaging|gust.speed|wind speed|extratropical|synoptic',r'阵风|平均时距'],
 'Q-PETW-1':[r'gust.front|peak factor|non.stationary|downburst|crossing|clustering',r'峰值|阵风锋'],
 'Q-PETW-2':[r'gust.front|non.stationary|downburst|averaging|time.varying',r'阵风|非平稳'],
 'Q-PETW-3':[r'evolutionary|time.frequency|wavelet|non.stationary|spectrum|spectral|downburst',r'时频|非平稳'],
 'Q-PETW-4':[r'equivalent.static|wind.load|gust.front.factor|non.stationary',r'等效静力|风荷载']}
# Hand-curated vocabulary for matching titles, then author tier and citation as tie breakers.
status_by={r['openalex_id']:r for r in stat}; allopen=[]
for r in records:
    if r['type']=='thesis' or r['has_fulltext']!='是':continue
    o=byoa.get(r['openalex_id'],{});allopen.append((r,o))
lines=['# 冻结检验题：来源候选（仅题名/元数据筛选）','',f'题面逐字来自 `{proj}` 第 55–62 行；不修改题面。候选仅表明题名相关、库内标记有全文，不表示正文已支持题目要求的数值、算法或适用界限。T1/T2 为写作来源代理标签而非真实性或作者贡献证明。','']
for q,question in qs:
    pats=patterns[q];scored=[]
    for r,o in allopen:
        title=r['title'];topic=r['topic'];score=sum(3 for pat in pats[0].split('|') if re.search(pat,title,re.I)) +sum(1 for pat in pats[1].split('|') if re.search(pat,topic,re.I))
        if score:scored.append((score,{'T1':3,'T2':2,'T3':1,'未知':0}[r['tier']],int(o.get('cited_by_count') or 0),r))
    scored.sort(key=lambda z:(-z[0],-z[1],-z[2],z[3]['title']))
    chosen=[z[3] for z in scored[:8]]
    # If the subject has no T1/T2 in its highest-ranked titles, do not quietly add irrelevant ones.
    lines.extend([f'## {q}',f'冻结问题：{question}',f'T1/T2 题名相关来源：{"有" if any(x["tier"] in ("T1","T2") for x in chosen) else "无；需 Lead 核实缺口或另选来源"}；能否实际支撑该题：待正文核验。下表均为全文标记为“是”的候选，精确答案及可引用页码未核。','', '| 作品 | 年份 | 层 | 依据线索 |','|---|---:|---|---|'])
    for x in chosen:lines.append(f'| {x["title"].replace("|","/")} ({x["work_id"] or x["openalex_id"]}) | {x["year"]} | {x["tier"]} | 题名关键词/主题粗分；作者序依据见 corpus_provenance.csv |')
    if not chosen:lines.append('| 暂无可靠候选 | | | 需重查元数据 |')
    if q=='Q-WX-2':lines.append('注意：候选中有飓风、非天气尺度风和下击暴流材料，均不能单凭题名外推为非对流冬季风暴的 ASOS/METAR 物理 QC 阈值；该题的特定阈值支撑目前未知。')
    if q=='Q-DWT-1':lines.append('注意：题名相关不代表给出 LES 数值声学噪声下 600 s 单记录不确定度；须核正文，当前无已证实的直接答案。')
    lines.append('')
(O/'questions_sources.md').write_text('\n'.join(lines),encoding='utf-8')
# Aggregate tables, avoid implying multiple topic labels are mutually exclusive.
D=['≤1999','2000–2009','2010–2019','≥2020','不详'];T=['T0','T1','T2','T3','未知'];count=collections.Counter((r['tier'],r['decade']) for r in records);full=collections.Counter((r['tier'],r['decade']) for r in records if r['has_fulltext']=='是')
lines=['# Kareem 写作来源分层（元数据代理，非作者贡献判定）','',f'OpenAlex r4 有效目录 {len([r for r in records if r["source"]=="OpenAlex+r4"])} 件（511 剔除 non_paper {exclusions["non_paper"]}、not_kareem {exclusions["not_kareem"]}、重复别名 {exclusions["duplicate"]}）；库存目录外 {len(extras)} 件；另外学位审计里未在 inventory 的 {len([r for r in records if r["source"]=="theses_in_library"])} 件。总 {len(records)} 行；r4 剔除项不在表内，库存额外行仍含课程资料及卷编辑，不可把总行数当论文件数。r4 为 10-19 快照，不含后续入库 v13–v19。','', '判层：≤2009 单作者/第一作者 T1；≤2009 其余或 ≥2010 单作者/第一作者 T2；≥2010 非第一作者 T3；无法确定年份或作者序为未知。学位单列 T0：未核本人硕士/疑似指导，已证实本人博士 T1、已证实指导的学生论文 T3（非署名）。末位或通讯是显示类别，判层时仍属非第一作者。综述/立场只标 invited_review 不改层。', '', '## 层 × 年代：总数／有全文数','', '| 层 | '+' | '.join(D)+' | 合计 |','|---|'+'---:|'*(len(D)+1)]
for t in T:
    lines.append('| '+t+' | '+' | '.join(f'{count[t,d]} / {full[t,d]}' for d in D)+f' | {sum(count[t,d] for d in D)} / {sum(full[t,d] for d in D)} |')
lines.extend(['','## T1 有全文：13 个主题分布（多标签，不能相加）',''])
topicstr=(P/'topic_map.md').read_text(encoding='utf-8'); topics=['非平稳风与雷暴风','阵风因子与峰值因子','高层建筑气动与风振','随机过程模拟与非高斯','数据驱动与机器学习','桥梁气动与颤振','可靠度与性能化设计','风浪/海洋结构','计算风工程与数值模型','结构控制与状态识别','风荷载与试验方法','信号处理与数值方法','教学讲稿与非论文材料']
for t in topics:lines.append(f'- {t}：{sum(t in r["topic"].split(";") for r in records if r["tier"]=="T1" and r["has_fulltext"]=="是")}（仅 inventory 中既有主题标签；目录其余作品尚未标主题）')
lines.extend(['','## T3 的 invited_review=是（题名/类型启发式，须 Lead 逐篇看）',''])
for r in records:
    if r['tier']=='T3' and r['invited_review']=='是':lines.append(f'- {r["year"]} {r["title"]}（{r["work_id"] or r["openalex_id"]}；全文 {r["has_fulltext"]}）')
lines.extend(['','## 单作者且有全文',''])
for r in records:
    if r['kareem_position']=='单作者' and r['has_fulltext']=='是':lines.append(f'- {r["year"]} {r["title"]}（{r["work_id"] or r["openalex_id"]}；{r["tier"]}）')
lines.extend(['','## KC 正式判断的来源层','',f'正式 57 条：最强 T1 {sum(x["best_tier"]=="T1" for x in kcs)}、T2 {sum(x["best_tier"]=="T2" for x in kcs)}、T3 {sum(x["best_tier"]=="T3" for x in kcs)}、未知 {sum(x["best_tier"]=="未知" for x in kcs)}；仅 T3 支持 {sum(x["only_T3"]=="是" for x in kcs)} 条（详见 kc_provenance.csv）。','', '## 局限','',f'- OpenAlex 作者 ID 未唯一定位的有效目录 {len(anomalies)} 条，未知；库存目录外作者顺序来自 inventory 文本，缺信息标未知。KRM-0186 是卷编辑非章节作者，保留账目行但层未知。','- 学位论文作为库存扩展行，不计入 r4 的论文覆盖率分母；学生学位论文非 Kareem 署名作品，不将导师关系说成写作贡献。theses_in_library 输入仅 7 件，项目页后续提及新入库的 Guo/Luo/Jayachandran 3 件未进入此 CSV，须更新学位目录后再生表。','- “有全文”沿用 r4/inventory/theses 元数据标记，未逐一打开 PDF；第三 EndNote 尚未正式合并入 r4 口径，后续批次未并入。','- invited_review 只按题名关键词或 OpenAlex review 类型打标，“invited”不保证真受邀；conference 也仅按类型/题名/刊物启发式。','- topic 只沿用 inventory 的旧标签，OpenAlex 中未匹配库存的作品没有主题，因此 T1 主题表是已标注子集，不是 T1 总主题分布。'])
(O/'provenance_summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(dict(rows=len(records),r4=476,extra=len(extras),thesis_extra=len([r for r in records if r['source']=='theses_in_library']),tiers=dict(collections.Counter(r['tier'] for r in records)),full=sum(r['has_fulltext']=='是' for r in records),kc=len(kcs),only_T3=sum(x['only_T3']=='是' for x in kcs),links=len(link),questions=len(qs),anomalies=len(anomalies)),ensure_ascii=False))
