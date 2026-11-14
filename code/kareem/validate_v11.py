#!/usr/bin/env python3
"""Verify v1.1 excerpt copies, source physical pages, pack parity and exam anchors."""
import csv,re,subprocess,collections
from pathlib import Path
from inspect_papers import P
from round2_candidates import EX
B=Path(__file__).parent
R={r['judgment_id']:r for r in csv.DictReader((B/'judgments_raw.csv').open(encoding='utf-8-sig'))}
staged={'KRM-0021':'04','KRM-0195':'05','KRM-0198':'06','KRM-0199':'07','KRM-0200':'08','KRM-0201':'09','KRM-0202':'10','KRM-0203':'11','KRM-0204':'12'}
cache={}
def pg(work,page):
 if work not in cache:
  path=str(EX[staged[work]] if work in staged else P[work][0]);raw=subprocess.run(['pdftotext','-raw',path,'-'],capture_output=True,text=True,check=True).stdout
  cache[work]=[re.sub(r'\s+',' ',re.sub(r'(?<=\w)-\s*\n(?=\w)','',s)) for s in raw.split('\f')]
 assert 0<int(page)<=len(cache[work]),(work,page)
 return cache[work][int(page)-1]
def blocks(s):return {int(m.group(1)):m.group(0) for m in re.finditer(r'^### KC-(\d\d)｜[\s\S]*?(?=^### KC-|^## |\Z)',s,re.M)}
check=(B/'Kareem_判断清单_v1.1.md').read_text();pack=(B/'review_pack_v1.1.md').read_text();q=(B/'考题_v1.1.md').read_text()
a=blocks(check.split('## 附录：')[0]);b=blocks(pack)
assert set(a)==set(b)==set(range(1,61))-{6,28,47}
assert len(re.findall(r'^## 题 \d\d',q,re.M))==20
assert not re.search(r'KC-(?:06|28|47)\b',q)
assert set(map(int,re.findall(r'KC-(\d\d)',q)))<=set(a)
errors=[];n=0;physical=0
for k,s in a.items():
 assert s.splitlines()[0]==b[k].splitlines()[0]
 source=re.search(r'^出处：(.*)$',s,re.M).group(1)
 assert '出处：'+source in b[k]
 refs={kid:(R[kid]['work_id'],R[kid]['pdf_page']) for kid in re.findall(r'KJ-\d+',source)}
 assert refs and all(R[kid]['keep']=='是' for kid in refs)
 quotes=re.findall(r'^逐字摘句（([^）]+)）：“([^”]*(?:”[^\n]*)?)”$',s,re.M)
 packquotes=re.findall(r'^摘句（([^）]+)）：“([^”]*(?:”[^\n]*)?)”$',b[k],re.M)
 if quotes!=packquotes:errors.append((k,'pack parity'))
 assert quotes,(k,'no quote')
 for anchor,quote in quotes:
  n+=1
  kid=re.search(r'KJ-\d+',anchor)
  if kid:
   kid=kid.group(); work,page=refs[kid]
   if quote!=R[kid]['quote_en']:errors.append((k,kid,'CSV quote differs'))
   if f'第 {page} 页' not in source and f'第 {page} 页' not in anchor:errors.append((k,kid,'page absent'))
  else:
   assert anchor.startswith('补充，PDF 物理第 '),(k,anchor)
   page=re.search(r'第 (\d+) 页',anchor).group(1);work=next(iter(refs.values()))[0]
  # line-wrap hyphen normalization as original validator, not spell/OCR repair
  if re.sub(r'\s+',' ',re.sub(r'(?<=\w)-\s*\n(?=\w)','',quote)) not in pg(work,page):errors.append((k,anchor,'PDF no match'))
  physical+=1
 # Each row used as support must be copied as a quote, to avoid a hidden unsupported clause.
 quoted={m.group() for anchor,_ in quotes for m in [re.search(r'KJ-\d+',anchor)] if m}
 if not quoted<=set(refs):errors.append((k,'quote without source'))
print('formal',len(a),'exam',len(re.findall(r'^## 题 \d\d',q,re.M)),'quote copies each',n,'PDF-page checks',physical,'works',len(cache),'errors',errors)
assert not errors
