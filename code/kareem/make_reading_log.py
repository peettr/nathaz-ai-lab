#!/usr/bin/env python3
"""Write an honest scope-specific reading log from validated rows."""
import csv,collections,subprocess,re
from pathlib import Path
from inspect_papers import R,P
B=Path(__file__).parent
rows=list(csv.DictReader(open(B/'judgments_raw.csv',encoding='utf-8-sig')))
c=collections.Counter(x['work_id'] for x in rows)
by=collections.defaultdict(set)
for x in rows:by[x['topic']].add(x['work_id'])
with open(B/'reading_log.md','w',encoding='utf-8') as f:
 f.write('# L22.5-02 判断抽取阅读记录（10-17）\n\n')
 f.write('读法：仅在本机只读打开 Zotero/EndNote 本地 PDF，以 pdftotext -raw 按物理页提取文本；逐篇核对首页题名、作者及可供判断的摘要/引言句，手工写一句中文判断并存原文摘句。PDF 物理页由文件的第 1 页起数，**本批 170 条均锚定首页**；没有把首页阅读冒称为全文逐页精读。另对优先四篇（0177、0083、0110、0171）预览了若干后文页，但本批未从后文收判断。`validate_judgments.py` 从原 PDF 第 1 页回查摘句逐字子串和页码，语义准确性仍待 Lead 抽样。未发原文给联网服务、外部模型或批量 Gemini。\n\n')
 f.write('共 '+str(len(rows))+' 条、'+str(len(c))+' 篇，不含台式机未公开幻灯；绝非每篇全文审阅。分组是本批判断所属主题而非库存主题图的重新清点；单篇可服务多个组。\n\n')
 f.write('| 主题 | 本批不同作品 |\n|---|---:|\n')
 for t,v in sorted(by.items()):f.write(f'| {t} | {len(v)} |\n')
 f.write('\n| work_id | 作品 | 抽取条数 | 阅读范围 |\n|---|---|---:|---|\n')
 for id in sorted(c):f.write(f'| {id} | {R[id]["title"].replace("|","/")} | {c[id]} | 本地 PDF 物理第 1 页：摘要、局部引言 |\n')
 f.write('\n读到首页但未收判断：KRM-0056（摘要主要介绍研究范围，未取宣示性结论）；KRM-0042 与 KRM-0141（仅为同题名前缀的去重核验）；KRM-0186（原 PDF 首页为 Patrick Hawbecker 章节、Kareem 为卷编辑，不作为其署名章节判断）。其余相似题名的台式机或缺附件条目本机无 PDF 首页，未声称读过。\n\n')
 f.write('风险与下一步：目前判断以首页摘要/局部引言为主，尚未对每篇全文及公式图表、限制段落做系统精读；部分原 PDF OCR 有词间粘连，未收不清楚的句子。期刊印刷页字段宁留空，不将 PDF 首页作期刊页。阶段 3 使用前须由 Lead 随机抽 30 条回 PDF 原页做语义审查（任务书门槛 ≥90%），再有针对性补读正文与结论；当前 CSV 是原始候选，不是冻结判断清单。\n')
print('reading log',len(c),len(rows))
