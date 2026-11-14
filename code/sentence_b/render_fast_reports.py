#!/usr/bin/env python3
"""Render local fast-path cluster metadata into traceable Markdown; no model calls."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
SUMMARIES = {
  1: ["未来设计风速与气候变化的研究题名或方法描述；多条来自参考文献，不构成方向性证据。", "极值/平均风速的统计与重分析线索；代表句大多是文献表或一般风速讨论。", "气候变化相关背景与气旋研究线索；该簇混入目录和宽泛背景。"],
  2: ["混合气候极值研究的引用线索；多条仅是文献标题，不能回答分开/合并的差值。", "雷暴/下击暴流可出现较高风速、与天气尺度风不同；尚无量化比较。", "雷暴观测与设计参数研究线索；大多是引用条目。"],
  3: ["雷暴风研究的参考文献线索；不直接讨论误分类。", "雷暴与非雷暴风对比、阵风因子及非平稳性的差别。", "混合气候极值研究的引用线索；不直接讨论标签错误。", "雷暴/下击暴流与天气尺度风特性不同，尚无误分类量化。", "漏掉雷暴事件或局地峰值可能低估设计风速，观测数据不足；未给偏差量级。", "分开统计的必要性及雷暴风资料收集线索；没有误分类误差传播估计。", "雷暴风廓线研究的引用线索。", "雷暴阵风气候学的引用线索。"]
}
for k in (1,2,3):
    d=json.loads((ROOT/f'B-{k}_fast_clusters.json').read_text())
    lines=[f'# B-{k} 句级聚类：FTS 候选快路（非全库结果）','',
           '本表是检索候选句的无监督分组，不代表全库文献的立场比例或经原文验证的结论。原文仅在本机保存。', '',
           f'候选页 {d["candidate_pages"]:,}；切得句子 {d["sentences"]:,}；语义选取去重后 N={d["retrieved"]}；聚为 {d["k"]} 簇。耗时 {d["seconds"]:.1f} 秒。',
           '候选页目前仅由 FTS5/BM25 获取，尚未合入既有页向量；这与 Lead 授权的双路候选有差异。',
           '方法：句向量多语言 MiniLM，L2 归一后 int8；余弦相似度保留前 1,000、逐字去重后最多 800；球面 k-means 固定种子 20261016，枚举 k=3..8，取 250 句近似 silhouette 最高且各簇至少五句者。代表句按簇心相似度、不同作品取五句。',
           '轮廓测试：'+', '.join(f'k={x["k"]}: {x["silhouette"]:.4f}' for x in d['tests'])+'。','',
           '注意：下列标题、年份和页码是附件元数据及 PDF 物理页；引用条目、目录与乱码仍被误收。要用作科学依据必须打开原 PDF 页复核。','']
    for c,summary in zip(d['clusters'],SUMMARIES[k]):
        lines += [f'## 簇 {c["cluster"]}（{c["size"]} 句，{c["work_count"]} 作品）','',
                  f'bot 概括：{summary}','']
        for i,r in enumerate(c['representatives'],1):
            text=r['text'].replace('\n',' ').strip()
            title=(r.get('title') or '无题').replace('\n',' ')
            lines += [f'{i}. “{text}” — {title}（{r.get("year") or "年不详"}），PDF 物理页 {r["physical_page"]}；attachment={r["attachment"]}，work={r["work"]}。']
        lines.append('')
    lines += ['原始小结果：台式机 `~/ftkb_sentences/fast/B-'+str(k)+'/clusters.json`；工作站 本目录 `B-'+str(k)+'_fast_clusters.json`。',
              '页级原样对照：`B-'+str(k)+'_pages.txt`（CLI 最多 -n 10）。','']
    target=ROOT/f'B-{k}.md'; target.write_text('\n'.join(lines),encoding='utf-8')
    print(target, len(d['clusters']), sum(len(c['representatives']) for c in d['clusters']))
