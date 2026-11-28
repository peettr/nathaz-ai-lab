#!/usr/bin/env python3
"""Curate second-round judgments from reviewed, local, physical PDF pages."""
import csv,collections,re
from pathlib import Path
from round2_candidates import pages,sentences,CUE,SELF,EX
from inspect_papers import R
B=Path(__file__).parent
P=B/'judgments_raw.csv'; rows=list(csv.DictReader(P.open(encoding='utf-8-sig')))
old=[x for x in rows if int(x['judgment_id'][3:])<=169]
assert len(old)==169 and len({x['judgment_id'] for x in old})==169
keep='1-5,7-9,11-17,20-24,27,29-30,33-34,39-40,42,44-45,47-48,50-54,56-59,61-63,65-67,70-71,76-77,79,81-82,84-88,97-99,101-103,107-109,110-112,114,118,121,129-130,132-134,137-138,141-142,146-150,156-159,162,166-168'
kept=set()
for z in keep.split(','):
 a,*b=z.split('-');kept.update(range(int(a),int(b[0])+1 if b else int(a)+1))
for x in old:
 n=int(x['judgment_id'][3:]);x['keep']='是' if n in kept else '否';x['reason']='' if n in kept else ('论文自述' if re.search(r'本(文|研究)|该(方法|框架|模型|方案)|提出|示例|案例|验证|可用|能够|可以|本次|以.*为例',x['judgment_zh']) else '偏具体结果/定义，缺少可迁移的领域判断');x['round']='1'
sel=[]
for line in (B/'round2_selections.tsv').read_text().splitlines():
 if not line or line.startswith('#'):continue
 a,zh,kind,topic=line.split('|');id,n,k=a.split(',');sel.append((id,int(n),int(k),zh,kind,topic))
assert len(set((id,n,k) for id,n,k,*_ in sel))==len(sel)
cache={};new=[];lookup={k:v for k,v in {'04':'KRM-0021','05':'KRM-0195','06':'KRM-0198','07':'KRM-0199','08':'KRM-0200','09':'KRM-0201','10':'KRM-0202','11':'KRM-0203','12':'KRM-0204'}.items()}
for id,pageno,idx,zh,kind,topic in sel:
 if id not in cache:cache[id]=pages(id)
 pp=cache[id]; assert 1<pageno<=len(pp),(id,pageno,len(pp))
 candidates=[s for s in sentences(pp[pageno-1]) if CUE.search(s) and not SELF.search(s) and len(s)<500]
 assert 0<idx<=len(candidates),(id,pageno,idx,len(candidates))
 quote=candidates[idx-1]; work=lookup.get(id,id);meta=R[work]
 if re.search(r'\b(references|bibliography)\b',pp[pageno-1][:100],re.I):raise ValueError(('reference-page',id,pageno))
 # Avoid overflow of sentences (numbers in OCR not reliably distinguishable, each selected is one sentence).
 pos=re.search(r'第(\d+)作者',meta['authors']);assert pos,(work,meta['authors'])
 new.append(dict(judgment_id=f'KJ-{170+len(new):04d}',topic=topic or meta['topic'].split(';')[0],judgment_zh=zh,quote_en=quote,work_id=work,title=meta['title'],year=meta['year'],pdf_page=str(pageno),journal_page='',type=kind,kareem_author_pos=pos.group(1),note=('第一作者非 Kareem；共同署名，不把主张归于单一作者' if pos.group(1)!='1' else '')+'；引文摘自正文/讨论/结论，不是首页摘要',keep='是',reason='',round='2'))
# Second semantic pass: keep only claims that remain actionable without a paper-specific antecedent.
weak={171,176,177,197,204,210,211,234,236,244,246,248,251,252,255,287,288,289}
for x in new:
 if int(x['judgment_id'][3:]) in weak:
  x['keep']='否';x['reason']='论文自述' if int(x['judgment_id'][3:]) in {204,246,287,288,289} else '代词/特定模型前提未在引文内交代；不能独立指导实践'
fields=['judgment_id','topic','judgment_zh','quote_en','work_id','title','year','pdf_page','journal_page','type','kareem_author_pos','note','keep','reason','round']
with P.open('w',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(old+new)
c=collections.Counter(x['topic'] for x in old+new if x['keep']=='是')
new_kept=sum(x['keep']=='是' for x in new)
print('old',len(old),'old_keep',len(kept),'new',len(new),'new_keep',new_kept,'total_keep',len(kept)+new_kept,'post-first-page-kept',new_kept,'papers',len(cache),'topics',dict(c))
assert len(kept)+new_kept>=150 and new_kept>=100 and min(c.values())>=6 and len(c)>=12
