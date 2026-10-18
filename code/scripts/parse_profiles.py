#!/usr/bin/env python3
import csv,json,re,collections,time,sys
from pathlib import Path
R=Path('./22_Lab/06_Logs/fulltext_kb')
TAG=sys.argv[1] if len(sys.argv)>1 else ''
a={x['id']:x for x in map(json.loads,open('./ftkb/profile_answers'+('_'+TAG if TAG else '')+'.jsonl'))}
m=[json.loads(s) for s in open(R/('profile_page_manifest'+('_'+TAG if TAG else '')+'.jsonl'))]
fields=['source_type','z_max','U_max','normalization','profile_model','model_parameters','r_over_D','figure_table']
rows=[]
for x in m:
    raw=a[x['key']]['response']; match=re.search(r'\{.*\}',raw,re.S)
    try:d=json.loads(match.group())
    except Exception:d={}
    row={k:x[k] for k in ['key','title','year','kind','page','pdf']}
    row.update({k:str(d.get(k,'') or '') for k in fields});row['evidence']=str(d.get('evidence',''));row['status']=a[x['key']]['status'];row['source']='本地 Zotero PDF；PDF 物理页；Gemini 3.8 Flash 单页文本提取，未经人工验证';rows.append(row)
p=R/('downburst_profiles_sample'+('_'+TAG if TAG else '')+'.csv')
with p.open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('rows',len(rows),'nonempty',collections.Counter(k for x in rows for k in fields if x[k]),'zero_primary',sum(not x['z_max'] and not x['U_max'] and not x['r_over_D'] for x in rows))
