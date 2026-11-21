#!/usr/bin/env python3
"""Audit stage-3 draft against immutable KJ source rows; run original PDF validator separately."""
import csv,re,collections
from pathlib import Path
B=Path(__file__).parent
R={r['judgment_id']:r for r in csv.DictReader(open(B/'judgments_raw.csv',encoding='utf-8-sig'))}
I={r['work_id']:r for r in csv.DictReader(open(B/'inventory.csv',encoding='utf-8-sig'))}
a=(B/'Kareem_判断清单_v1.md').read_text();p=(B/'review_pack.md').read_text();e=(B/'考题草稿.md').read_text()
pat=r'^### (KC-\d+)｜([^\n]+)\n(.*?)(?=^### KC-|^## [^#]|\Z)'
A=re.findall(pat,a,re.M|re.S);P=re.findall(pat,p,re.M|re.S)
assert len(A)==len(P)==60
assert [x[0] for x in A]==[x[0] for x in P]==[f'KC-{i:02d}' for i in range(1,61)]
c=collections.Counter();single=front=quotes=0;bad=[]
for (id,zh,b),(pid,pzh,pb) in zip(A,P):
 assert id==pid and zh==pzh
 topic=re.search(r'^主题：([^；]+)',b,re.M).group(1);c[topic]+=1
 all_ids=re.findall(r'KJ-\d+',re.search(r'^出处：(.*)$',b,re.M).group(1))
 all_ids_p=re.findall(r'KJ-\d+',re.search(r'^出处：(.*)$',pb,re.M).group(1))
 assert all_ids==all_ids_p and all_ids and len(all_ids)==len(set(all_ids))
 assert not {'KJ-0138','KJ-0103','KJ-0070'}&set(all_ids)
 assert all(R[x]['keep']=='是' for x in all_ids)
 assert all(f"《{R[x]['title']}》PDF 物理第 {R[x]['pdf_page']} 页" in b for x in all_ids)
 assert all(f"《{R[x]['title']}》PDF 物理第 {R[x]['pdf_page']} 页" in pb for x in all_ids)
 if len({R[x]['work_id'] for x in all_ids})==1:single+=1;assert '证据单一' in b
 if any(R[x]['round']=='1' for x in all_ids):front+=1
 for block in [b,pb]:
  m=re.search(r'(?:逐字摘句|摘句)（(KJ-\d+)）：“([^\n]+)”',block)
  assert m,(id,block)
  kid,quote=m.groups();assert kid in all_ids
  assert quote==R[kid]['quote_en'],(id,kid)
  assert len(re.findall(r'[.!?](?:\s|$)',quote))<=2
  if R[kid]['round']=='1' and any(R[x]['round']=='2' for x in all_ids):bad.append((id,'round1 chosen over round2'))
  quotes+=1
 assert '为什么：' in b and '适用条件：' in b and '演变/分歧：' in b
assert len(c)==12 and single==56 and front==9 and not bad,bad
Q=re.findall(r'^## 题 (\d+)（([^）]+)）\n(.*?)(?=^## 题 |\Z)',e,re.M|re.S)
assert len(Q)==20 and [int(x[0]) for x in Q]==list(range(1,21))
for n,t,b in Q:
 assert all(v in b for v in ('题干：','标准答案：','判分要点：','出处：','难度：'))
 ids=re.findall(r'KC-\d+',b);assert len(ids)==1 and ids[0] in {x[0] for x in A}
 # Questions contain no English excerpts; only source citations and page numbers.
 assert not re.search(r'逐字摘句|quote_en',b)
print('stage3 PASS: KC',len(A),'topics',dict(c),'single-work',single,'with-round1',front,'exact-quote-copies',quotes,'exam',len(Q),'banned-KJ',0)
