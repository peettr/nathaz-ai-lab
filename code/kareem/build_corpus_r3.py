#!/usr/bin/env python3
"""Read-only batch-4 reconciliation. Writes new r3 artifacts only; no network/PDF reads."""
import ast,csv,collections,pathlib,re,unicodedata
P=pathlib.Path(__file__).resolve().parent
SOURCE=pathlib.Path('./.hermes/profiles/researchos-literature/artifacts/kareem_round4/kareem_127_total_results.csv')
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def norm(s):return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower())
def doi(s):return re.sub(r'^https?://(?:dx\.)?doi\.org/','',(s or '').lower().strip())
def save(name,rows,fields):
 with (P/name).open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def append(r,s):r['note']+=(('；' if r['note'] else '')+s)
rows=read(P/'corpus_status_r2.csv');intake=read(SOURCE); inv={r['work_id']:r for r in read(P/'inventory.csv')}
for r in rows:r['round4_result']='';r['round4_reason']=''
assert len(rows)==511 and len(intake)==127
bydoi=collections.defaultdict(list);bytitle=collections.defaultdict(list)
for r in rows:
 if doi(r['doi']):bydoi[doi(r['doi'])].append(r)
 if norm(r['title']):bytitle[norm(r['title'])].append(r)
matched=[]; seen=set()
for x in intake:
 k=doi(x['doi']); cand=bydoi[k] if k else bytitle[norm(x['title'])]
 assert len(cand)==1,(x['title'],x['doi'],[z['openalex_id'] for z in cand])
 r=cand[0];assert r['openalex_id'] not in seen,r['openalex_id'];seen.add(r['openalex_id'])
 assert norm(x['title'])==norm(r['title']) or norm(x['title'])[:45]==norm(r['title'])[:45],(x['title'],r['title'])
 result=x['result'];assert result in ('imported','blocked','other')
 # 15 abbreviation identities are resolved in batch 4 (97 imported + 5 blocked + other cases).
 if r['status']=='not_kareem' and r['author_verification']=='仅缩写A. Kareem，身份未定':
  r['status']='不在库';r['author_verification']='第四批核实为Ahsan Kareem（来源回执）';append(r,'第三批暂排除撤销：第四批身份已核')
 r['round4_result']=result;r['round4_reason']=x['reason'];r['intake_batch']+=(';fourth' if r['intake_batch'] else 'fourth')
 if result=='imported':
  assert all(x[y] for y in ('zotero_parent_key','pdf_child_key','local_pdf_path')) and pathlib.Path(x['local_pdf_path']).is_file(),x['title']
  assert r['status'] in ('不在库','库内有全文'),(r['title'],r['status'])
  r['status']='库内有全文';r['access_result']='attached_verified';r['zotero_parent_key']=x['zotero_parent_key'];r['pdf_child_key']=x['pdf_child_key'];r['pdf_path']=x['local_pdf_path'];append(r,'第四批已附目标PDF（本次仅核暂存路径存在；不代表Windows同步）')
 else:
  if r['status']!='库内有全文':r['access_result']='round4_'+result
  append(r,'第四批'+result+'：'+x['reason'][:200])
 matched.append((r,result))
assert collections.Counter(y for _,y in matched)=={'imported':97,'blocked':5,'other':25}
assert sum(r['author_verification']=='第四批核实为Ahsan Kareem（来源回执）' for r in rows)==15
# Exclude obvious session/group headings, reviews of another article, front matter and placeholder, not substantive articles.
nonpaper_ids={
 'W2009414157':'会议分组标题','W2069719864':'会议组织分组标题','W2399942969':'会议分组标题','W2399958065':'会议组织分组标题',
 'W4239202974':'Invited Lectures 合集标题','W4247438979':'Invited Lectures 合集标题',
 'W3128887920':'同行评审 Author response','W4247251011':'同行评审 Author response',
 'W2063071366':'Discussion of session 分组材料','W3022334080':'Discussion of session 分组材料',
 'W4230780163':'Foreword 前言','W4234731735':'Concluding Summary 章节尾声','W4241040364':'Introduction 章节前言','W4245971582':'空白题名目录记录'
}
for r in rows:
 id=r['openalex_id'].split('/')[-1]
 if id in nonpaper_ids:
  assert not r['duplicate_of'] and r['status'] in ('不在库','not_kareem'),(id,r['status'])
  r['status']='non_paper';append(r,'非独立研究论文：'+nonpaper_ids[id]+'；不计分母')
assert sum(r['status']=='non_paper' for r in rows)==len(nonpaper_ids)
active=[r for r in rows if not r['duplicate_of'] and r['status'] not in ('not_kareem','non_paper')]
cnt=collections.Counter(r['status'] for r in active);assert set(cnt)=={'库内有全文','库内只有题录','不在库'}
script=ast.parse((P/'build_corpus_status.py').read_text())
topics=next(ast.literal_eval(n.value) for n in script.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='topics' for t in n.targets))
bydec=collections.defaultdict(collections.Counter);bytopic=collections.defaultdict(collections.Counter)
for r in active:
 dec=str(int(r['year'])//10*10)+'s' if r['year'].isdigit() else '年不详';bydec[dec][r['status']]+=1
 labels=[x for x in inv[r['work_id']]['topic'].split(';') if x in topics or x=='风工程综合/其他待细分'] if r['work_id'] in inv else [t for t,rx in topics.items() if re.search(rx,r['title'],re.I)]
 for t in (labels or ['风工程综合/其他待细分']):bytopic[t][r['status']]+=1
# Untouched r2 "not in library" and without any third/fourth intake attempts. Batch 2 attempts are deliberately not interpreted as "third/fourth".
fetch=sorted((r for r in active if r['status']=='不在库' and not any(x in r['intake_batch'].split(';') for x in ('third_A','third_B','third_C','fourth'))),key=lambda r:(-int(r['cited_by'] or 0),r['openalex_id']))
# Shortlist: only items with an explicit failed/blocked or identity-incomplete access record, and directly on the six specified topics.
relevance=re.compile(r'gust.front|gust front|thunderstorm|downburst|non.stationary|nonstationary|peak factor|equivalent static|time.frequency|time.frequency|wavelet',re.I)
problems=[r for r in active if r['status']!='库内有全文' and relevance.search(r['title']) and (r['round4_result'] in ('blocked','other') or r['access_result'] in ('source_tested_no_verified_pdf','publisher_gate_not_tested','pending_pdf_identity','rejected_wrong_pdf','rejected_wrong_version','pending_bibliographic_identity'))]
problems.sort(key=lambda r:(0 if r['round4_result']=='blocked' else 1 if r['round4_result']=='other' else 2,-int(r['cited_by'] or 0),r['openalex_id']))
short=[]
for r in problems[:10]:
 reason=r['round4_reason'] if r['round4_result'] in ('blocked','other') else r['note'].split('；')[-1]
 route='学校账号浏览器下载；若不通则馆际互借' if '403' in reason or '出版社' in reason or '安全验证' in reason else '先核题录/目标版本；学校账号浏览器下载或馆际互借'
 short.append(dict(title=r['title'],year=r['year'],doi=r['doi'],cited_by=r['cited_by'],reason=reason,suggested_route=route,openalex_id=r['openalex_id']))
fields=list(rows[0]);save('corpus_status_r3.csv',rows,fields)
save('to_fetch_r5.csv',[dict(title=r['title'],year=r['year'],doi=r['doi'],oa_url=r['oa_url'],cited_by=r['cited_by'],openalex_id=r['openalex_id']) for r in fetch],['title','year','doi','oa_url','cited_by','openalex_id'])
save('for_Liang Hu_short.csv',short,['title','year','doi','cited_by','reason','suggested_route','openalex_id'])
def table(c):return f"{c['库内有全文']} | {c['库内只有题录']} | {c['不在库']} | {sum(c.values())}"
with (P/'corpus_summary_r3.md').open('x',encoding='utf-8') as f:
 f.write('# Kareem 目录对库第三轮（第四批并入）\n\n来源：OpenAlex 冻结作者目录 A5069470138（511 ID）及 `corpus_status_r2.csv`；Literature 第四批 `kareem_127_total_results.csv`（97 imported / 5 blocked / 25 other），`build_corpus_r3.py` 只读处理。PDF 暂存路径仅验存在，来源批次报告称目标附件已核验；未复核哈希及 Zotero Windows 同步，不下载。\n\n')
 f.write(f"目录原始 {len(rows)}；重复别名 {sum(bool(r['duplicate_of']) for r in rows)}；非独立论文 non_paper {len(nonpaper_ids)}；非 Kareem {sum(r['status']=='not_kareem' for r in rows)}；分母 {len(active)}（仍为 OpenAlex 目录候选，不是全部真实作品）。第四批将原暂排 15 条 A. Kareem 身份按来源核实为本人并恢复，但其中 Invited Lectures 是 non_paper，故只将其余计入论文分母。\n\n")
 f.write(f"当前有全文 {cnt['库内有全文']}（{cnt['库内有全文']/len(active):.1%}）、只有题录 {cnt['库内只有题录']}（{cnt['库内只有题录']/len(active):.1%}）、不在库 {cnt['不在库']}（{cnt['不在库']/len(active):.1%}）；题录覆盖 {(cnt['库内有全文']+cnt['库内只有题录'])/len(active):.1%}。第一轮原口径 511：116/9/386，全文 22.7%、题录 24.5%；第二轮暂定口径 494：152/9/333，全文 30.8%、题录 32.6%。**三轮分母不同，百分比不能解释为纯补全文增量。** 第四批 97 imported 中包括第三批先前暂排的身份记录，不等于当前全文数净增 97。\n\n")
 f.write('non_paper 清单（保留 OpenAlex 行、剔出论文分母；仅按目录题名/类型判定，未逐篇首页核对）：\n\n| OpenAlex ID | 题名 | 理由 |\n|---|---|---|\n')
 for r in rows:
  if r['status']=='non_paper':f.write(f"| {r['openalex_id']} | {r['title'].replace('|','/')} | {nonpaper_ids[r['openalex_id'].split('/')[-1]]} |\n")
 f.write('\n## 按年代缺口\n\n| 年代 | 有全文 | 只有题录 | 不在库 | 总计 |\n|---|---:|---:|---:|---:|\n')
 for k in sorted(bydec):f.write(f'| {k} | {table(bydec[k])} |\n')
 f.write('\n## 按主题缺口（题名粗分，多标签不可相加）\n\n已匹配库存的作品沿用 inventory 主题；其余沿用 `build_corpus_status.py` 的 13 组题名正则，其他待细分不算实质领域。\n\n| 主题 | 有全文 | 只有题录 | 不在库 | 总计 |\n|---|---:|---:|---:|---:|\n')
 for k in [*topics,'风工程综合/其他待细分']:f.write(f'| {k} | {table(bytopic[k])} |\n')
 f.write(f'\n## 下一批与 Liang Hu 短清单\n\n`to_fetch_r5.csv` {len(fetch)} 条：限仍不在库、第三及第四批均无处理记录的目录 ID；按 OpenAlex 快照被引排序。未将 OA 空值判定为无法获取；第二批或库存历史尝试不在此“第三/四批未尝试”定义之内。`for_Liang Hu_short.csv` {len(short)} 条：上述六方向的当前未得目标全文、且有明确来源受阻/身份待核记录；“拿不到”仅指本轮未得到已验证目标 PDF，不表示学校账号及馆际互借已穷尽，更无证据标“只能向作者要”。未联系任何人。\n\n')
 f.write('限制：目录有同题异 DOI 未解决组，第三 EndNote 库仍未纳入，桌面机远端文件未逐件核；部分 OA 为落地页而非 PDF。候选分母与主题均需在补库及元数据核验后重算。\n')
assert len(rows)==511 and len({r['openalex_id'] for r in rows})==511
assert len(active)+sum(bool(r['duplicate_of']) for r in rows)+sum(r['status']=='not_kareem' for r in rows)+len(nonpaper_ids)==511
assert sum(cnt.values())==len(active) and all(r['round4_result']=='' and r['status']=='不在库' for r in fetch)
assert all(r['pdf_path'] and r['zotero_parent_key'] and r['pdf_child_key'] for r in rows if r['round4_result']=='imported')
print('active',len(active),'counts',dict(cnt),'non_paper',len(nonpaper_ids),'fetch',len(fetch),'Liang Hu_short',len(short),'round4',collections.Counter(r['round4_result'] for r in rows if r['round4_result']))
