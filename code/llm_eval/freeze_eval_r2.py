"""Freeze once before any model run; after freeze never edit questions."""
import json,hashlib,re,collections
from pathlib import Path
p=Path(__file__).parent
assert not (p/'eval_set_r2.jsonl').exists(),'Frozen set already exists: never overwrite'
a=[json.loads(x) for x in (p/'eval_ac_r2_draft.jsonl').read_text().splitlines()];b=[json.loads(x) for x in (p/'eval_b_r2_draft.jsonl').read_text().splitlines()]
allrows=sorted(a+b,key=lambda r:(r['group'],int(r['id'].split('_')[1])))
assert collections.Counter(r['group'] for r in allrows)=={'A2':200,'B2':50,'C2':100}
assert len({r['id'] for r in allrows})==350 and len({r['source_key'] for r in allrows if r['group']=='A2'})==200
assert collections.Counter(r['answer'] for r in allrows if r['group']=='A2')=={'是':50,'否':150}
assert len({r['card'] for r in b})>=15 and sum(r['table']>0 for r in b)>=20
for x in allrows:
 assert x['answer'] is not None and len(x['prompt'])>50
 if x['group']=='B2':assert str(x['page']) in x['source'] and x['card'] and x['unit']
path=p/'eval_set_r2.jsonl';path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in allrows))
sha=hashlib.sha256(path.read_bytes()).hexdigest()
baseA=lambda x:'是' if re.search(r'downburst|microburst|thunderstorm|outflow|gust front',x['prompt'].split('摘要：',1)[1],re.I) else '否'
baseC=lambda x:'Thunderstorm Wind' if re.search(r'\b(thunderstorm|tstm|t-storm|convective|squall line|downburst|microburst|supercell|outflow boundary|storm cell)\b',x['prompt'].split('叙述：',1)[1],re.I) else '非对流性大风'
na=sum(baseA(x)==x['answer'] for x in allrows if x['group']=='A2');nc=sum(baseC(x)==x['answer'] for x in allrows if x['group']=='C2')
assert na<190,'A2 >=95%, reject/rebuild before model run'
(p/'labels_provenance_r2.md').write_text(f'''# 第二轮冻结标签与来源（建集前审题）\n\n数据集：eval_set_r2.jsonl；SHA-256 `{sha}`；A2=200（正50/负150），B2=50（15篇PDF，其中22题表格），C2=100（Thunderstorm Wind 50，High Wind 30，Strong Wind 20）。标题、标签和来源字段不给模型，只发 prompt。所有模型同一题面，不得跑后改题；如发现问题题只剔除并保留原始输出。\n\nA2：公开论文 Zotero 元数据摘要关联 LitWiki 卡片中的 Zotero key；正例首选 cfd_m4_downburst_cfd/paper_cards 与 windfield_step2/papers，负例为一般CWE、WRF、EVA、加速风洞、结构响应等近邻卡片；同 DOI/同 Zotero key 去重。人工审标题及摘要时排除负例中的实际风场模拟/观测及正例中的荷载/响应/综述；具体剔除 key 见 build_eval_r2.py。标签为本次人工筛选判断，个别近邻摘要仍可能有歧义（不得作为真理）。A2 简单主题词基线：{na}/200，{na/200:.1%}，未达95%上限。来源卡片的绝对路径和 key 均逐题记录。\n\nB2：沿用第一轮的7篇25个已核 PDF 页数值；新增8篇25个，卡片 Quantitative anchor ledger 明载数值、页码；脚本 build_pdf_r2.py 同时核查该数值存在原 Zotero PDF 对应物理页，且22个新增表格题检查 Table 标号在页内。各题记录 card / PDF路径 /物理页 /单位 / table 号。题目只给 pdftotext -layout 页文字，无法从文本恢复的图中数值未选。最初25题不是本轮新独立题（存在第一轮模型见过的可能），分数必须说明混用历史题的限制。评分预定：单位相同或等价且数值相对误差≤1%。\n\nC2：NCEI Storm Events 官方 d2019/d2021/d2023/d2024 详情 CSV，各年归档 URL 和 EVENT_ID 逐题记录；仅 Thunderstorm Wind、High Wind、Strong Wind，州和年份分层，描述140–1400字。跑模型前排除：事件叙述直接出现完整事件类型短语；仅说损坏而没有成因提示；对流/非对流成因同时出现的叙述。正例需叙述内对流成因线索，负例需非对流性气象成因线索，此为预筛规则，可能造成词汇捷径。宽关键词规则基线：{nc}/100；若满分，该组无法检验语义模型相对规则的增量，应明确标注不可据此判可接走。字段名不在模型提示中，叙述内容原样，不遮蔽正文中的天气现象。原 EVENT_TYPE 是行政归档标签，非气象事件的独立再判定。\n\n判据在模型运行前固定：A2 本地模型召回≥95%且精确率≥前沿最好精确率的70%；B2/C2 本地最好≥前沿最好分数90%且明显胜过关键词基线（B2无适用的关键词数值抽取基线，须注明该条件不可判）。每组单独评价，95% CI 用 Wilson 二项式区间；吞吐包括冷启动/下载。D取消。\n''')
print('FROZEN',len(allrows),sha,'baseline A',na,'C',nc)
