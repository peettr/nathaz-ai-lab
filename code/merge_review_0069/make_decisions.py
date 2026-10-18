import json,csv,collections,sqlite3,re,hashlib
from pathlib import Path
root=Path(__file__).parent
rs=list(map(json.loads,open(root/'diagnostics.jsonl')))
assert len(rs)==127
# Explicit reviewer dispositions for the misleading shared-title/shared-cover clusters.
NO={
1:'同一 ICWE12 的 Volume 1 与 Volume 2：前页共用大会资料，后续文章不同（全库正文匹配仅 15 页），不合并两卷。',
3:'BBAA7 两篇不同论文：第 1 页分别是 added mass of circular membrane 与 wind pressure on flat-roofed buildings；pdfinfo 标题误导。',
4:'ICWE14 模板题名重复，首篇为 Joplin tornado fragilities，另一篇为 Australian housing insurance loss；正文不同。',
20:'五份不同卷/期的 JWEIA 单页刊物说明复用相同版面；期号不同，不能凭通用刊物页合并作品。',
21:'56 份 Davenport symposium 各有独立 AGD-RP 编号与不同文章正文；统一会议封面/元数据不是同一论文。',
48:'三份 Bimba 产品目录前四页通用，随后产品型号与页数不同（60/39/49 页），非同一目录版本。',
49:'同一书拆出的不同章节（b10991-11 与 b10991-8）：分别为参考文献页和第 7 章，非重复文件。',
50:'同一书第 2 章与第 3 章单独 PDF，首两页正文与章节号均不同。',
51:'同一书第 8 章与第 5 章单独 PDF，首两页正文与章节号均不同。',
52:'同一书第 7 章与第 6 章单独 PDF，首两页正文与章节号均不同。',
69:'Ass3 作业题与 Ass3_solns 解答首两页相同，但后者多出解答正文（6 页对 2 页），不作重复副本合并。',
74:'同一本书的 22 份分章 PDF，首两页章节号/正文各异；共同 pdfinfo 书名不是同一文档。',
75:'一本 662 页全书和一份 22 页 Chapter 1 抽取版（21 页内容重合）：粒度不同，不合并检索作品。',
76:'同名 Chapter 18 两份修订稿：第 5–9 页正文、篇幅（12/11 页）不同；不能仅凭前两页合并版本。',
78:'一本 354 页全书和一份 10 页 TOC 摘录：共享目录但作品粒度不同，不合并。',
89:'AS/NZS 1170.2:2002 标准本体（106 页）与 Supp 1:2002 commentary（181 页）不同；pdfinfo 共用题名。',
126:'SSReader Print 五页摘录与《弹性稳定理论》569 页全书前几页重合；部分页与整书非同一文件作品。',
127:'MFC 第 1–5 部分仅共享前三页版权声明；后续各篇章节与页数不同，不能合并分册。',
}
# The two ABAQUS lecture packs share much of the body but differ in pagination, missing/added pages and identifiers;
# refrain from forcing a merge without a verified edition identity.
UNSURE={70:'两份 ABAQUS geotechnical lectures 有约 282 页正文逐字相同，但 442/451 页、插入页及页序不同；未查明是否同一修订版本，暂不合并。'}
assert not set(NO)&set(UNSURE)
# Read-only secondary verification of the Zotero/EndNote/Desktop cross-library cluster.
c=sqlite3.connect('file:./ftkb/index.sqlite?mode=ro',uri=True)
rv=rs[4]; d=sqlite3.connect('file:./ftkb_desktop/page_text_v2.sqlite?mode=ro',uri=True)
txt=d.execute('select text from pages where sha256=? and physical_page=1',(rv['shas'][0],)).fetchone()[0]
for key in ('27UQJJRP','END-82c9b79e999242e6'):
 t=c.execute('select text from pages where attachment=? and page=1',(key,)).fetchone()[0]
 assert re.sub(r'\W+','',t.casefold())==re.sub(r'\W+','',txt.casefold()),key
rows=[]
for r in rs:
 n=r['n']; ps=r['pairs']; counts=[p['common'] for p in ps]
 if n in NO:decision='不合并';why=NO[n]
 elif n in UNSURE:decision='拿不准';why=UNSURE[n]
 elif n==5:decision='合并';why='Desktop 与 Zotero 27UQJJRP、EndNote END-82c9b79e999242e6 首页面正文规范化逐字一致，簇另有同一已核 DOI 10.1016/0167-6105(78)90019-3。'
 elif counts and min(counts)>=2:
  decision='合并';why=f'逐组核首几页：成员两两至少 {min(counts)} 页非短篇正文逐字相同（页文本≥350 字符）；属同一内容副本。'
 elif counts and min(counts)==1 and all(p['sim']==1 for p in ps):
  decision='合并';why='均为单页短文档：物理第 1 页完整正文规范化逐字相同，非仅题名/期刊抬头一致。'
 else:raise RuntimeError(f'Unreviewed {n} {r["work"]} {counts}')
 rows.append({'组号':n,'实验室 WORK id':r['work'],'成员 DSK id':' | '.join(r['ids']),'判定':decision,'依据':why})
with open(root/'merge_decisions.csv','w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
ct=collections.Counter(r['判定'] for r in rows)
assert sum(ct.values())==127
assert sum(len(r['成员 DSK id'].split(' | ')) for r in rows)==337
(root/'summary.md').write_text(f'''# 0069 作品合并待核队列（实验室只读核验）\n\n来源：`./platform/reports/ftkb_desktop_merge_queue.md`（127 组）；实验室 `work_clusters_v2.csv` 将 DSK 前缀映射至 SHA-256；`./ftkb_desktop/page_text_v2.sqlite` 与 `./ftkb/index.sqlite` 均以只读 URI 打开。判定详见 `merge_decisions.csv`，每行一组、列出组内全部 DSK id；只供平台人工参考，不是对索引写入的授权。\n\n组数：{len(rows)}；DSK 成员：337；合并 {ct['合并']}，不合并 {ct['不合并']}，拿不准 {ct['拿不准']}。\n\n核验方法：比对各文件首六页及非短页（≥350 规范化字符）的逐字哈希；再检查明显冲突的标题、章节/卷号、成员页数、文件路径及代表性全书的正文重合。原队列 `first_two_pages_exact_engine_specific` 仅是候选线索，不能自动把公共封面/版权页、目录与书章混为一件作品。单页文档要求完整正文逐字相同；同一出版社的单页通用刊物说明因不同卷/期单独保留。Zotero/EndNote 交叉组另用原有 ftkb 只读索引逐字核首面。`diagnostics.jsonl` 保留首面摘要、前六页重合数与相似度；`analyze_queue.py` 与 `make_decisions.py` 可复核。\n\n重点：第 1 组 ICWE12 两卷共享前页但后文不同；第 3–4 组元数据错把不同论文题名标成相同；第 21 组 56 篇 Davenport 会议论文不合并；第 48 组三册 Bimba 产品目录前四页相同但后文不同；第 49–52、74、127 组属于分章/分册；第 89 组标准与补充说明是不同文档。第 70 组 ABAQUS 讲义大量相同但版本/插页不明，单列拿不准，维持不合并。\n\n判定边界：不同字节但同一论文的完整正文副本可建议合并；此建议并非平台规则中的 Crossref 核验本身。若平台仅准同 SHA、Crossref 核实 DOI/题名(+年份)三种合并依据，则其余“合并”行应先补独立元数据核验，不能把本表正文相同当作平台规则已满足。\n''',encoding='utf-8')
print(dict(ct),'rows',len(rows),'members',sum(len(r['成员 DSK id'].split(' | ')) for r in rows))
