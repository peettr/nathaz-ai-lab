#!/usr/bin/env python3
"""Select one physical PDF page per downburst profile paper; no PDF upload."""
import csv,json,re,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from ftkb import source_items
ROOT=Path('./22_Lab/06_Logs/fulltext_kb')
DATA=Path('./ftkb/downburst_pages.jsonl')
pat=re.compile(r'(vertical (?:velocity|wind.speed|profile)|velocity profile|wind.speed profile|radial velocity profile|height of (?:maximum|peak)|maximum (?:horizontal|radial) (?:velocity|speed)|z.max|zmax|u.max|vicroy|oseguera|wood et al)',re.I)
chosen=[]
c=sqlite3.connect('file:./ftkb/index.sqlite?mode=ro',uri=True)
for key,title,year,ak,pdf,page,text in c.execute('SELECT key,title,year,attachment,pdf,page,text FROM pages WHERE lower(title) LIKE "%downburst%" OR lower(title) LIKE "%microburst%" OR lower(title) LIKE "%impinging jet%" OR lower(title) LIKE "%thunderstorm outflow%"'):
    matches=list(pat.finditer(text))
    if len(text.strip())<300 or not matches:continue
    score=len(matches)+2*bool(re.search(r'Fig(?:ure)?\.?\s*\d+',text,re.I))+bool(re.search(r'\d+(?:\.\d+)?\s*(?:m/s|m s|mm|cm|met(?:er|re)|m\b)',text,re.I))
    kind=('CFD' if re.search(r'numerical|simulation|CFD|LES',title,re.I) else '风洞' if re.search(r'experimental|physical|wind tunnel|facility|impinging jet',title,re.I) else '实测/其他')
    chosen.append(dict(key=key,title=title,year=year,attachment=ak,pdf=pdf,page=page,kind=kind,text=text[:13500],score=score))
chosen=sorted(chosen,key=lambda x:-x['score'])
chosen=list({x['key']:x for x in reversed(chosen)}.values())
chosen.sort(key=lambda x:-x['score'])
DATA.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in chosen))
chosen.sort(key=lambda x:-x['score'])
selected=[]
for kind,quota in [('CFD',12),('风洞',12),('实测/其他',12)]:
    selected += [x for x in chosen if x['kind']==kind][:quota]
selected=selected[:36]
(ROOT/'profile_page_manifest.jsonl').write_text(''.join(json.dumps({k:v for k,v in x.items() if k!='text'},ensure_ascii=False)+'\n' for x in selected))
prompt='''只读下面这篇论文的单个 PDF 物理页，绝不可假设看过别页。仅提取本页明确支持的下击暴流水平/径向风速竖向廓线信息；严格 JSON，不要 markdown：{"source_type":"实测/风洞/CFD/不明","z_max":"原文值+单位或空","U_max":"原文值+单位或空","normalization":"原文定义或空","profile_model":"原文名称或空","model_parameters":"原文参数或空","r_over_D":"原文数值或空","figure_table":"原文图表号或空","evidence":"每个非空值的原文短引句；不得捏造"}。无明确数值留空；图像曲线未提供，不得根据文本臆读图上点。PDF 物理页：{page}。标题：{title}。页面文字：\n{text}'''
(Path('./ftkb/profile_prompts.jsonl')).write_text(''.join(json.dumps({'id':x['key'],'prompt':prompt.replace('{page}',str(x['page'])).replace('{title}',x['title']).replace('{text}',x['text'])},ensure_ascii=False)+'\n' for x in selected))
print('candidates',len(chosen),'selected',len(selected),'types',[(k,sum(x['kind']==k for x in selected)) for k in ['CFD','风洞','实测/其他']])
