#!/usr/bin/env python3
"""Second, stricter sample: own paper's figure caption containing vertical profile."""
import json,re,sqlite3,collections
from pathlib import Path
R=Path('./22_Lab/06_Logs/fulltext_kb')
c=sqlite3.connect('file:./ftkb/index.sqlite?mode=ro',uri=True)
q="""select key,title,year,attachment,pdf,page,text,type from pages where (lower(title) like '%downburst%' or lower(title) like '%microburst%' or lower(title) like '%impinging jet%' or lower(title) like '%thunderstorm%') and (lower(text) like '%vertical profile%' or lower(text) like '%velocity profile%')"""
pat=re.compile(r'(?:fig(?:ure)?\.?\s*\d[^.]{0,100}(?:vertical|velocity|wind speed) profile|(?:vertical|velocity|wind speed) profile[^.]{0,100}fig(?:ure)?\.?\s*\d)',re.I)
items={}
for key,title,year,ak,pdf,page,text,typ in c.execute(q):
 if typ not in ('journalArticle','conferencePaper'):continue
 m=pat.search(text)
 if not m:continue
 caption=text[max(0,m.start()-90):m.end()+150]
 score=5*bool(re.search(r'(?:fig(?:ure)?\.?\s*\d[^.]{0,55}(?:vertical|velocity) profile)',caption,re.I))+len(re.findall('vertical profile|velocity profile',text,re.I))+int(page>2)
 kind='CFD' if re.search(r'numerical|simulation|CFD|LES',title,re.I) else '风洞' if re.search(r'experimental|wind tunnel|impinging jet|physical',title,re.I) else '其他/待核'
 row=dict(key=key,title=title,year=year,attachment=ak,pdf=pdf,page=page,kind=kind,score=score,caption=caption,text=text[:12000])
 if key not in items or score>items[key]['score']:items[key]=row
selected=[]
for kind,n in [('CFD',12),('风洞',14),('其他/待核',10)]:
 selected.extend(sorted((x for x in items.values() if x['kind']==kind),key=lambda x:-x['score'])[:n])
assert len(selected)==36,len(selected)
with (R/'profile_page_manifest_v2.jsonl').open('x') as f:
 for x in selected:f.write(json.dumps({k:v for k,v in x.items() if k!='text'},ensure_ascii=False)+'\n')
prompts=[]
for x in selected:
 text='只分析下面这篇论文的PDF物理页（没有图像），不要用其他页或常识。请只抽取本页讨论的下击暴流水平/径向风速竖向廓线，JSON字段 source_type,z_max,U_max,normalization,profile_model,model_parameters,r_over_D,figure_table,evidence；每项只填原文字面支持的数值/单位和定义，别页数据与所引文献不能当本论文测值；缺值留空。没有曲线像素，不能猜图读。题名：'+x['title']+'；PDF页：'+str(x['page'])+'；候选图注：'+x['caption']+'。页文字：'+x['text']
 prompts.append(dict(id=x['key'],prompt=text))
with Path('./ftkb/profile_prompts_v2.jsonl').open('x') as f:
 for x in prompts:f.write(json.dumps(x,ensure_ascii=False)+'\n')
print('papers',len(selected),'categories',dict(collections.Counter(x['kind'] for x in selected)))
print(*[(x['key'],x['page'],x['kind'],x['title'][:50]) for x in selected],sep='\n')
