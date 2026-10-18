#!/usr/bin/env python3
"""Reconcile frozen Kareem catalog with read-only Literature intake; write new r2 files only."""
import ast, collections, csv, pathlib, re, unicodedata
P=pathlib.Path(__file__).resolve().parent
Q=pathlib.Path('./16_PETW/05_Literature_Wiki/99_Scratch')
def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(name,fields,rows):
    path=P/name
    if path.exists():raise FileExistsError(path)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def norm(s):return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower())
def doi(s):return re.sub(r'^https?://(?:dx\.)?doi\.org/','',(s or '').lower().strip())
def append(r,text):r['note']=(r['note']+'；' if r['note'] else '')+text
base=read(P/'corpus_status.csv');extra=read(P/'corpus_status_extra.csv');inv=read(P/'inventory.csv')
rows=[dict(x, zotero_parent_key='',pdf_child_key='',pdf_path='',intake_batch='',access_result='',author_verification='') for x in base]
bydoi=collections.defaultdict(list);bytitle=collections.defaultdict(list)
for r in rows:
    if r['doi']:bydoi[doi(r['doi'])].append(r)
    bytitle[norm(r['title'])].append(r)
used=set();exceptions=[]
def target(x):
    cand=bydoi.get(doi(x['doi']),[]) if x.get('doi') else bytitle.get(norm(x['title']),[])
    if len(cand)!=1:exceptions.append((x['title'],x.get('doi'),len(cand)));return None
    return cand[0]
# Parse the second-batch markdown: these 18 DOI rows are stable; no PDF is fetched.
md=(Q/'Kareem18_intake_status_20261017_v2.md').read_text(encoding='utf-8')
second=[]
for line in md.splitlines():
    if not re.match(r'^\|\s*\d+\s*\|',line):continue
    cells=[c.strip() for c in line.strip().strip('|').split('|')]
    if len(cells)<5:continue
    match=re.search(r'`(10\.[^`]+)`',cells[2]);key=re.search(r'parent `([A-Z0-9]+)`',cells[4]);child=re.search(r'child `([A-Z0-9]+)`',cells[4]);pdf=re.search(r'`(./',cells[4])
    # Keys and paths are in the result cell (cells[3]), not explanation.
    result=cells[3];key=re.search(r'parent `([A-Z0-9]+)`',result);child=re.search(r'child `([A-Z0-9]+)`',result);pdf=re.search(r'`(./',result)
    if match:second.append((match.group(1),result,key.group(1) if key else '',child.group(1) if child else '',pdf.group(1) if pdf else ''))
assert len(second)==18,len(second)
for d,result,key,child,pdf in second:
    r=target({'doi':d,'title':''});
    if not r:continue
    r['intake_batch']='second';r['zotero_parent_key']=key;r['pdf_child_key']=child;r['pdf_path']=pdf
    if '已入库' in result:
        assert key and child and pdf
        r['status']='库内有全文';r['access_result']='attached_verified';append(r,'第二批：云端附件+暂存PDF已在来源批次散列核验；不等于Windows已同步')
    else:
        assert key
        if r['status']=='不在库':r['status']='库内只有题录'
        r['access_result']='bibliography_only';append(r,'第二批 Zotero 仅题录，无经验证目标全文')
# Third A/B/C; verified attachment is stronger than a later failed candidate link.
for file,batch in [('kareem_round3_A_20261018.csv','third_A'),('kareem_round3_B_20261018.csv','third_B'),('kareem_round3_C_v6_20261018.csv','third_C')]:
    for x in read(Q/file):
        r=target(x)
        if not r:continue
        state=x['access_result'];r['intake_batch']+=';'+batch if r['intake_batch'] else batch
        if state=='excluded_non_author':
            r['author_verification']='仅缩写A. Kareem，身份未定' if re.search(r'\bA\.?\s+Kareem\b',x.get('verified_authors',''),re.I) and 'Abdel Kareem' not in x.get('verified_authors','') else '其他姓名（非Ahsan）'
            r['status']='not_kareem';r['access_result']=state
            append(r,'第三批C暂标非目标作者；15条A. Kareem缩写仍待身份核实，剔除仅为按委托的暂定口径')
            continue
        if state=='attached_verified':
            if not (x['zotero_parent_key'] and x['pdf_child_key'] and x['local_pdf_path']):exceptions.append((x['title'],x['doi'],'缺附件字段'));continue
            r['status']='库内有全文';r['access_result']=state;r['zotero_parent_key']=x['zotero_parent_key'];r['pdf_child_key']=x['pdf_child_key'];r['pdf_path']=x['local_pdf_path']
            append(r,'第三批'+batch[-1]+'：已核验附件；暂存路径，不等于Windows本地同步')
        else:
            if r['status']!='库内有全文':r['access_result']=state
            append(r,'第三批'+batch[-1]+'：'+state+'；'+x['reason'][:180])
# Re-examine 76 extra records: only unique title suffix/truncation with an acquired, identity-checked PDF promoted.
# The other variants are retained in extra for version/remote first-page review, not guessed away.
manual={'KRM-0007':('W2014251158','题名是唯一长前缀（截断台式机标题）；第三批A目标PDF首页身份已核；远端副本仍未核')}
extra_r=[]
for x in extra:
    if x['work_id'] in manual:
        wid,reason=manual[x['work_id']];r=next(y for y in rows if y['openalex_id'].endswith(wid))
        assert not r['work_id'] and r['status']=='库内有全文'
        r['work_id']=x['work_id'];r['match_basis']='人工';append(r,reason);used.add(x['work_id']);continue
    y=dict(x);y['review_result']='未合并：仅元数据不足以证明同作';y['candidate_openalex_id']=''
    if x['work_id'] in ('KRM-0001','KRM-0017','KRM-0146'):
        ids={'KRM-0001':'W4239812720','KRM-0017':'W1997212598','KRM-0146':'W2961393171'}
        y['candidate_openalex_id']='https://openalex.org/'+ids[x['work_id']];y['review_result']='近题/缺年候选：OpenAlex 已连另一本地work_id；需要原件首页与版本核对，不双配'
    elif x['work_id'] in ('KRM-0002','KRM-0019','KRM-0049','KRM-0164','KRM-0184'):
        ids={'KRM-0002':'W1971619005','KRM-0019':'W2106293516','KRM-0049':'W4242860576','KRM-0164':'W3198497352','KRM-0184':'W3217295356'}
        y['candidate_openalex_id']='https://openalex.org/'+ids[x['work_id']]
        y['review_result']='题名近似或相同但年份/版本/文种冲突；缺原件首页，暂不合并'
    extra_r.append(y)
# One defensible DOI alias: identical title/year/authors/venue, .abs only changes landing-page suffix.
parent=next(r for r in rows if r['openalex_id'].endswith('W2010952808'))
alias=next(r for r in rows if r['openalex_id'].endswith('W4244098435'))
assert parent['title']==alias['title'] and parent['year']==alias['year'] and alias['doi']==parent['doi']+'.abs'
alias['duplicate_of']=parent['openalex_id'];append(alias,'同作者题名年份刊物；.abs 摘要落地页 DOI 别名；原件首页未取得，目录级合并')
for ids in [('W2015745637','W2912514826'),('W2052830150','W4244972401')]:
 for r in rows:
    if any(r['openalex_id'].endswith(i) for i in ids):append(r,'同题异DOI：首页不可得；前组可能记录错配，后组article/书章不同版本；不合并')
fields=list(rows[0]);write('corpus_status_r2.csv',fields,rows)
write('corpus_status_extra_r2.csv',list(extra_r[0]),extra_r)
# Compute summary from counted, unique, provisionally author-eligible directory IDs only.
active=[r for r in rows if not r['duplicate_of'] and r['status']!='not_kareem']
cnt=collections.Counter(r['status'] for r in active);assert sum(cnt.values())==len(active)
missing=[r for r in active if r['status']=='不在库']
script=ast.parse((P/'build_corpus_status.py').read_text())
topics=next(ast.literal_eval(n.value) for n in script.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='topics' for t in n.targets))
local={r['work_id']:r for r in inv};by_dec=collections.defaultdict(collections.Counter);by_topic=collections.defaultdict(collections.Counter)
for r in active:
    dec=str(int(r['year'])//10*10)+'s' if r['year'].isdigit() else '年不详'
    by_dec[dec][r['status']]+=1
    labels=[a for a in local[r['work_id']]['topic'].split(';') if a in topics or a=='风工程综合/其他待细分'] if r['work_id'] else [t for t,rx in topics.items() if re.search(rx,r['title'],re.I)]
    for t in (labels or ['风工程综合/其他待细分']):by_topic[t][r['status']]+=1
# 'Unobtainable' is a current access worklist, not an impossible-to-acquire finding.
problems=[]
for r in active:
    if r['status']=='库内有全文':continue
    ar=r['access_result']
    if ar in ('source_tested_no_verified_pdf','publisher_gate_not_tested','pending_pdf_identity','rejected_wrong_pdf','rejected_wrong_version','pending_bibliographic_identity','not_acquired','bibliography_only'):
        if ar=='source_tested_no_verified_pdf':reason='已测所给/OA来源，无经验证目标PDF'
        elif ar=='publisher_gate_not_tested':reason='出版社安全验证门，目标PDF未测试'
        elif ar=='pending_pdf_identity':reason='候选PDF身份未确认，未附'
        elif ar=='rejected_wrong_pdf':reason='候选PDF错文'
        elif ar=='rejected_wrong_version':reason='候选PDF非该版本'
        elif ar=='pending_bibliographic_identity':reason='题录身份待核'
        else:reason='目前仅题录或来源报告未获合格PDF'
        route='学校账号浏览器下载' if ar in ('publisher_gate_not_tested','not_acquired','source_tested_no_verified_pdf') else '馆际互借'
        if r['type']=='其他:book' or 'Springer' in r['venue']:route='学校账号浏览器下载 / 馆际互借'
        problems.append(dict(title=r['title'],year=r['year'],doi=r['doi'],cited_by=r['cited_by'],reason=reason,suggested_route=route,openalex_id=r['openalex_id'],access_result=ar,oa_url=r['oa_url'],selection='第三批/第二批未获验证全文'))
selected={r['openalex_id'] for r in problems}
nooa=sorted((r for r in missing if not r['oa_url'] and r['openalex_id'] not in selected),key=lambda r:-int(r['cited_by']))[:50]
for r in nooa:
    problems.append(dict(title=r['title'],year=r['year'],doi=r['doi'],cited_by=r['cited_by'],reason='OpenAlex快照无OA链接；尚未逐来源测试，非不可获得证明',suggested_route='学校账号浏览器下载 / 馆际互借',openalex_id=r['openalex_id'],access_result=r['access_result'],oa_url='',selection='无OA链接缺口按被引补至前50'))
write('unobtainable_for_Liang Hu.csv',list(problems[0]),problems)
# Keep the top-50 no-link list defined globally (including prior attempts), and annotate any rows already included.
global50=sorted((r for r in missing if not r['oa_url']),key=lambda r:-int(r['cited_by']))[:50]
assert len(global50)==50
missing_ids={r['openalex_id'] for r in problems}
assert {r['openalex_id'] for r in global50}<=missing_ids, 'All global no-OA top50 must be represented'
first_keys={'PXRJNXFA','Y2R9SZST','45ZGKKUP','IJVHR8TV','CWMTBVI5','DTWMZIUV','ZJG9R4HA','39FRDPCX','QTTNCUKF'}
first=[x for x in inv if set(x['library_item_ids'].split(';'))&first_keys]
assert len(first)==9 and all(x['has_fulltext']=='是' for x in first)
with (P/'corpus_summary_r2.md').open('x',encoding='utf-8') as f:
    f.write('# Kareem 目录对库第二轮（暂定口径）\n\n来源：第一轮 `corpus_status.csv` 与 `inventory.csv`；Literature 的 `Kareem18_intake_status_20261017_v2.md`、第三批 A/B/C_v6 CSV；OpenAlex 冻结作者目录 A5069470138。脚本 `build_corpus_r2.py`。仅对题录和只读的批次回执复算，未下载全文或重验云端附件；附件PDF路径是 Literature 暂存副本，不等于 Windows Zotero 已同步。\n\n')
    f.write('## 分母与第一轮对比\n\n')
    f.write(f'原目录 511 ID；本轮确认目录级 `.abs` 别名重复 1；按委托将 C 表的 `excluded_non_author` 16 条暂标 `not_kareem` 剔出（和别名互不重叠）；暂定分母 {len(active)}。状态：有全文 {cnt["库内有全文"]}（{cnt["库内有全文"]/len(active):.1%}）、只有题录 {cnt["库内只有题录"]}（{cnt["库内只有题录"]/len(active):.1%}）、不在库 {cnt["不在库"]}（{cnt["不在库"]/len(active):.1%}）；题录覆盖 {(cnt["库内有全文"]+cnt["库内只有题录"])/len(active):.1%}。第一轮口径 511、116/9/386，全文覆盖 22.7%，题录覆盖 24.5%。不应将此称为已核实真实独立作品数。\n\n')
    f.write('关键纠偏：Literature 第三批状态说明 v4 明确 16 个 `excluded_non_author` 中，15 个作者表为 A. Kareem 缩写，尚不能断言不是 Ahsan Kareem；仅 1 个为其他 Kareem 姓名。上面的剔除是执行委托的**暂定分母**，不是科学上的作者身份裁决。若保留这 15 个待定身份，备选分母 '+str(len(active)+15)+'，缺口 '+str(cnt['不在库']+15)+'；待核实作者全名后重算。\n\n')
    f.write(f'首批 9 篇的 Zotero key 全在 inventory、均标全文；第二批 18 件中 8 PDF、10 仅题录；第三批 A/B/C 各 3/10/16 条经验证附件（跨批次存在重合，例如 C 与第二批 DesignSafe，逐作品去重）。新增的 `pdf_path` 是来源回执路径，状态优先采用已验证 PDF，不被后续来源尝试失败覆盖。目录之外本地原 76 件，人工对上 {len(used)} 件，剩余 {len(extra_r)} 件见 `corpus_status_extra_r2.csv`（不计目录覆盖率；本地低置信度、旧版本/会议版待核）。\n\n')
    f.write('三组第一轮同题异 DOI：W2010952808 与 W4244098435 的 `.abs` 摘要落地页别名依同题同作者同年同刊目录证据合并（非首页确认）；屋面压力 W2015745637/W2912514826 的 DOI 不同，疑元数据错配，原件首页不可得，未合并；LES W2052830150/W4244972401 分属期刊与书章不同 DOI，未合并。详见主表 note。\n\n')
    f.write('## 按年代缺口（未匹配目录项）\n\n| 年代 | 有全文 | 只有题录 | 不在库 | 总计 |\n|---|---:|---:|---:|---:|\n')
    for k in sorted(by_dec):
        c=by_dec[k];f.write(f'| {k} | {c["库内有全文"]} | {c["库内只有题录"]} | {c["不在库"]} | {sum(c.values())} |\n')
    f.write('\n## 按主题缺口（13 组加未细分）\n\n沿用第一轮 `build_corpus_status.py` 的题名正则；已匹配库存者沿用 inventory 标签。允许多标签，组间不可相加；未细分并非具体领域。\n\n| 主题 | 有全文 | 只有题录 | 不在库 | 总计 |\n|---|---:|---:|---:|---:|\n')
    for k in [*topics,'风工程综合/其他待细分']:
        c=by_topic[k];f.write(f'| {k} | {c["库内有全文"]} | {c["库内只有题录"]} | {c["不在库"]} | {sum(c.values())} |\n')
    f.write(f'\n## 当前未拿到的工作单\n\n`unobtainable_for_Liang Hu.csv` 共 {len(problems)} 行，含第三批失败、未确认与第二批仅题录，以及不在库无 OA 链接的全局被引前 50（重合者不重复）；这不代表永久不可获得。建议优先学校账号浏览器，继以馆际互借；标“只能向作者要” {sum("只能向作者要" in x["suggested_route"] for x in problems)} 件：无合法渠道穷尽证据，不作此断言。未联系任何人。\n\n')
    f.write('局限：第三 EndNote 库未并入；台式机全文远端未逐件核验；15 个缩写作者身份待核；缺 DOI/跨年作品和不同版不可强并；后续 Zotero 云端同步状态未重验。缺口状态为题录与回执快照。\n')
# invariant checks after writing
assert len(rows)==511 and len({r['openalex_id'] for r in rows})==511
assert all(not r['work_id'] or r['work_id'] in local for r in rows)
assert len(extra_r)+len(used)==76
assert len(active)==sum(cnt.values()) and len(active)+sum(r['status']=='not_kareem' for r in rows)+sum(bool(r['duplicate_of']) for r in rows)==511
assert all(r['pdf_path'] and r['zotero_parent_key'] and r['pdf_child_key'] for r in rows if r['access_result']=='attached_verified')
print('rows',len(rows),'active',len(active),'status',dict(cnt),'extra',len(extra_r),'manual',len(used),'unobtainable',len(problems),'first9',len(first),'exceptions',exceptions)
