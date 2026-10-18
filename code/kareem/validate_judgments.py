#!/usr/bin/env python3
"""Deterministic physical-page, verbatim-quote, schema and inventory audit."""
import csv,re,subprocess,collections
from pathlib import Path
from inspect_papers import R,P
from round2_candidates import EX,sentences,pages as get_pages
B=Path(__file__).parent
rows=list(csv.DictReader(open(B/'judgments_raw.csv',encoding='utf-8-sig')))
cols=['judgment_id','topic','judgment_zh','quote_en','work_id','title','year','pdf_page','journal_page','type','kareem_author_pos','note','keep','reason','round']
assert list(rows[0])==cols
assert len({x['judgment_id'] for x in rows})==len(rows)
staged={'KRM-0021':'04','KRM-0195':'05','KRM-0198':'06','KRM-0199':'07','KRM-0200':'08','KRM-0201':'09','KRM-0202':'10','KRM-0203':'11','KRM-0204':'12'}
assert all(x['work_id'] in R and (x['work_id'] in P or x['work_id'] in staged) and x['pdf_page'].isdigit() and x['quote_en'] and x['judgment_zh'] for x in rows)
assert all(R[x['work_id']]['unpublished']=='否' and x['keep'] in ('是','否') and x['round'] in ('1','2') for x in rows)
problems=[];by=collections.defaultdict(list)
for x in rows:by[x['work_id']].append(x)
for id,xs in by.items():
 path=str(EX[staged[id]] if id in staged else P[id][0])
 raw=subprocess.run(['pdftotext','-raw',path,'-'],capture_output=True,text=True,check=True).stdout
 pp=[p for p in raw.split('\f') if p.strip()]
 for x in xs:
  pg=int(x['pdf_page']); t=pp[pg-1] if 0<pg<=len(pp) else ''
  # Check exact glyph sequence after ONLY linebreak dehyphenation and whitespace collapse.
  t=re.sub(r'(?<=\w)-\s*\n(?=\w)','',t);t=re.sub(r'\s+',' ',t)
  if x['quote_en'] not in t:problems.append((x['judgment_id'],'no-exact-match',x['quote_en'][:70]))
  if len(re.findall(r'[.!?](?:\s|$)',x['quote_en']))>2:problems.append((x['judgment_id'],'over-two-sentences',''))
  if x['title']!=R[id]['title'] or x['year']!=R[id]['year']:problems.append((x['judgment_id'],'metadata-mismatch',''))
  if x['round']=='2' and pg==1:problems.append((x['judgment_id'],'second-round-front-page',''))
print('entries',len(rows),'PDFs',len(by),'page-errors',problems)
assert not problems
