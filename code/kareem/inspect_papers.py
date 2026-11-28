#!/usr/bin/env python3
"""Local PDF page-window inspection; never writes extracted source text."""
import json,csv,subprocess,re,sys
from pathlib import Path
B=Path(__file__).parent
R={x['work_id']:x for x in csv.DictReader(open(B/'inventory.csv',encoding='utf-8-sig'))}
P={x['id']:x['paths'] for x in map(json.loads,open(B/'source_paths.jsonl'))}
E=list(csv.DictReader(open(B.parent/'fulltext_kb/desktop_inventory/metadata/endnote_records_v3.csv',encoding='utf-8-sig')))
for e in E:
 for id,x in R.items():
  if e['record_id'] in x['library_item_ids']:
   paths=[s for s in e['pdf_paths'].split(';') if Path(s).is_file()]
   if paths:P.setdefault(id,paths)
cue=re.compile(r'\b(however|should|must|necessary|recommend|suggest|important|limitation|limited|cannot|not only|critical|advantag|pitfall|need |ought |essential|unlike|in contrast|we propose|this paper|in summary|in conclusion|conclud|demonstrat|therefore|may not|rather than)\b',re.I)
if __name__=='__main__':
 for id in sys.argv[1].split(','):
  print('\n========',id,R[id]['title'],'========')
  if id not in P:print('MISSING PDF');continue
  path=P[id][0]; out=subprocess.run(['pdftotext','-raw',path,'-'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True).stdout
  pages=out.split('\f'); pages=[x for x in pages if x.strip()];print('PAGES',len(pages),'AUTH',R[id]['authors'])
  for n,p in enumerate(pages,1):
   if len(sys.argv)>2 and sys.argv[2].isdigit() and n>int(sys.argv[2]):break
   paras=[re.sub(r'\s+',' ',x).strip() for x in re.split(r'\n\s*\n',p)]; hit=[s for s in paras if len(s)>45 and cue.search(s)]
   print('\nPDF PAGE',n)
   for para in hit[:(int(sys.argv[3]) if len(sys.argv)>3 else 4)]:print('-',para[:650])
