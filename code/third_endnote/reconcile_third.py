#!/usr/bin/env python3
"""Conservative local-title reconciliation; no external writes or requests."""
import csv,re,difflib,unicodedata
from pathlib import Path
from collections import Counter,defaultdict
B=Path(__file__).parent; ROOT=B.parent

def load(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def norm(s):
 s=unicodedata.normalize('NFKD',s or '').casefold();s=s.replace('fft','fourier transform') if False else s
 return re.sub(r'[^a-z0-9]','',s)
def doi(s):return (s or '').lower().replace('https://doi.org/','').strip()
third=load(B/'third_refs.csv');inv=load(ROOT/'inventory.csv');corpus=load(ROOT/'corpus_status_r4.csv')
kr=[r for r in third if re.search(r'\bkareem\b',r['author'],re.I)]

def score(r,c):
 a=norm(r['title']);b=norm(c['title']);
 if not a or not b:return 0
 yr=r['year'];cy=c['year']; yd=abs(int(yr)-int(cy)) if yr and cy and yr.isdigit() and cy.isdigit() else 9
 if doi(r['doi']) and doi(r['doi'])==doi(c.get('doi','')):return 1.0
 if a==b:return .99 if yd<=2 else .93
 ratio=difflib.SequenceMatcher(None,a,b).ratio()
 if a in b or b in a: ratio=max(ratio,.87 if min(len(a),len(b))>=28 else .5)
 if yd>2:ratio-=.08
 return ratio
out=[]
for r in kr:
 cs=sorted(((score(r,c),c) for c in corpus),key=lambda x:x[0],reverse=True)
 ins=sorted(((score(r,c),c) for c in inv),key=lambda x:x[0],reverse=True)
 cscore,c=cs[0];iscore,i=ins[0]
 # A unique exact title or DOI gives direct match; near title is explicitly provisional.
 accepted=cscore>=.985 and (len(cs)==1 or cscore>cs[1][0]+.002)
 invok=iscore>=.985 and (len(ins)==1 or iscore>ins[1][0]+.002)
 candidate=f"{c['openalex_id']} ({cscore:.3f})" if cscore>=.78 else ''
 if accepted:
  cat='OpenAlex 已有全文' if c['status']=='库内有全文' else ('OpenAlex 只有题录' if c['status']=='库内只有题录' else 'OpenAlex 不在库')
 elif invok:cat='仅 inventory 已有（未对上 OpenAlex）'
 else:cat='未对上（含近题待核）' if cscore>=.78 or iscore>=.78 else '未对上'
 o=dict(r,comparison=cat,openalex_id=c['openalex_id'] if accepted else '',corpus_status=c['status'] if accepted else '',work_id=i['work_id'] if invok else (c['work_id'] if accepted else ''),match_basis='题名归一化+年份' if accepted else ('inventory 题名归一化+年份' if invok else '未确认'),candidate_openalex=candidate,candidate_inventory=f"{i['work_id']} ({iscore:.3f})" if iscore>=.78 else '',match_note='' if accepted else ('近似题名/年份候选不作自动合并' if candidate else ''))
 out.append(o)
cols=['record_id','author','year','title','journal','volume','pages','doi','image','link_to_pdf','has_file','file_relpath','match_confidence','comparison','openalex_id','corpus_status','work_id','match_basis','candidate_openalex','candidate_inventory','match_note']
with (B/'kareem_reconciliation.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows({k:r.get(k,'') for k in cols} for r in out)
new=[r for r in out if r['has_file']=='是' and r['comparison'] in ('OpenAlex 不在库','OpenAlex 只有题录','未对上','未对上（含近题待核）')]
with (B/'new_with_file.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows({k:r.get(k,'') for k in cols} for r in new)
print('category',Counter(r['comparison'] for r in out),'new file',len(new));
for r in new:print(r['record_id'],r['comparison'],r['title'][:62],r['candidate_openalex'],r['candidate_inventory'])
