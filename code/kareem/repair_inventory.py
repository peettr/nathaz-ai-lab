#!/usr/bin/env python3
"""Stage-2 authorized inventory correction, retaining stable IDs for survivors."""
import csv,re,collections
from pathlib import Path
B=Path(__file__).parent
P=B/'inventory.csv'
rows=list(csv.DictReader(open(P,encoding='utf-8-sig',newline='')))
by={r['work_id']:r for r in rows}
# Both copies' PDF page 1 independently reopened; keep cited published Zotero ID.
for gone,keep,reason in [
 ('KRM-0085','KRM-0086','两库 PDF 首页同题名/作者及摘要；EndNote 题名多 A'),
 ('KRM-0053','KRM-0054','两库 PDF 首页同题名/作者及摘要；EndNote DOI 尾缺右括号'),
 ('KRM-0081','KRM-0080','两库 PDF 首页同题名/作者及摘要；EndNote DOI 尾缺右括号')]:
 a,b=by[gone],by[keep]
 b['library_item_ids']=';'.join(dict.fromkeys((b['library_item_ids']+';'+a['library_item_ids']).split(';')))
 b['libraries']=';'.join(dict.fromkeys((b['libraries']+';'+a['libraries']).split(';')))
 b['has_fulltext']='是' if '是' in (a['has_fulltext'],b['has_fulltext']) else '否'
 b['dedup_note']='; '.join(filter(None,[b['dedup_note'],f'阶段2首页核验合并 {gone}→{keep}：{reason}']))
 rows.remove(a)
# Journal articles mistakenly labelled teaching by title substring.
for r in rows:
 labels=r['topic'].split(';')
 if '教学讲稿与非论文材料' in labels and r['doi'] and r['venue']:
  labels.remove('教学讲稿与非论文材料')
  if r['work_id']=='KRM-0116': labels.append('数据驱动与机器学习')
  r['topic']=';'.join(dict.fromkeys(labels))
  r['dedup_note']='; '.join(filter(None,[r['dedup_note'],'阶段2：有 DOI/期刊的论文，纠正误分教学材料']))
 if r['work_id']=='KRM-0077':
  r['topic']='风荷载与试验方法'
  r['dedup_note']='; '.join(filter(None,[r['dedup_note'],'Global living laboratory 的出版类型未核；不据题名断定课程材料']))
 r['unpublished']='是' if ('Desktop' in r['libraries'].split(';') and re.search(r'powerpoint|\.pptx?\b|class\b',r['title'],re.I)) else '否'
# Unresolved similar titles: original remote inaccessible or dates/abstracts differ.
remarks={
 'KRM-0001':'与 KRM-0069 同题但台式机首页本机不可读、年份缺；暂不合并',
 'KRM-0017':'与 KRM-0124 同题但台式机首页本机不可读、年份缺；暂不合并',
 'KRM-0042':'与 KRM-0141 不同：PDF 首页 1991 FFT 与 2017 hybrid stochastic wave/POD，DOI 不同',
 'KRM-0139':'与 KRM-0140 题名近似，PDF 本机缺失，暂不合并',
 'KRM-0159':'与 KRM-0183 不同年份 2019/2021、研究对象 tall buildings/bluff bodies；旧 PDF 缺，暂不合并',
 'KRM-0165':'与 KRM-0166 题名/方法不同，PDF 本机缺失，暂不合并',
}
for id,n in remarks.items():
 r=by[id];r['dedup_note']='; '.join(filter(None,[r['dedup_note'],'阶段2近题核验：'+n]))
 if id=='KRM-0042':by['KRM-0141']['dedup_note']+='; 阶段2近题核验：与 KRM-0042 不同论文'
cols=list(rows[0]);assert len(rows)==194
with open(P,'w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,cols);w.writeheader();w.writerows(rows)
with open(B/'README.md','a',encoding='utf-8') as f:
 f.write('\n## L22.5-02 阶段二修订（10-17）\n原清单 197 件，回 EndNote/Zotero 本地 PDF 首页核验后合并 3 组（0085→0086、0053→0054、0081→0080），现 194 件，work_id 保留原号、不重新顺排；具体首页与不能核实组见 `inspect_pairs.py`、inventory 的 dedup_note。另 0042/0141 首页年份、题名、方法和 DOI 均不同，不并。0001/0069、0017/0124 的台式机首页本机不能读；0139/0140 两 PDF 不可读；0159/0183 老 PDF 不可读且年份/题名不同；0165/0166 两 PDF 不可读，均不硬合并。纠正 DOI/期刊论文 0116、0136、0176、0178 的误设教学标签，Global living laboratory 出版类型未知，不按教学材料下结论。`unpublished=是` 标记台式机 PowerPoint/课程幻灯，不用于判断抽取；台式机文件仍未本机核验。修订后主题图原文件为阶段一快照，篇数未随本次修订重算，使用 inventory 为准。\n')
print('works',len(rows),'fulltext',collections.Counter(x['has_fulltext'] for x in rows),'unpublished',collections.Counter(x['unpublished'] for x in rows))
