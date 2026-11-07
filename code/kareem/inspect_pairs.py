import json,csv,subprocess,re
from pathlib import Path
B=Path(__file__).parent
r={x['work_id']:x for x in csv.DictReader(open(B/'inventory.csv',encoding='utf-8-sig'))}
p={x['id']:x['paths'] for x in map(json.loads,open(B/'source_paths.jsonl'))}
end=list(csv.DictReader(open(B.parent/'fulltext_kb/desktop_inventory/metadata/endnote_records_v3.csv',encoding='utf-8-sig')))
for e in end:
 for id,x in r.items():
  if e['record_id'] in x['library_item_ids'] and e['pdf_paths']:
   paths=[s for s in e['pdf_paths'].split(';') if Path(s).is_file()]
   if paths:p.setdefault(id,paths)
pairs=[('KRM-0085','KRM-0086'),('KRM-0001','KRM-0069'),('KRM-0017','KRM-0124'),('KRM-0042','KRM-0141'),('KRM-0053','KRM-0054'),('KRM-0080','KRM-0081'),('KRM-0139','KRM-0140'),('KRM-0159','KRM-0183'),('KRM-0165','KRM-0166')]
for aa,bb in pairs:
 print('\n###',aa,bb)
 for id in (aa,bb):
  x=r[id];print(id,x['title'],'YEAR',x['year'],'DOI',x['doi'],'IDS',x['library_item_ids'])
  if id in p:
   path=p[id][0]; txt=subprocess.run(['pdftotext','-f','1','-l','1','-layout',path,'-'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True).stdout
   print('PDF',path,'PAGE1:',re.sub(r'\s+',' ',txt)[:900])
  else:print('PDF unavailable locally')
