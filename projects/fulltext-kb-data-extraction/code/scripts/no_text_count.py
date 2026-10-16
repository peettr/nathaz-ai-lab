#!/usr/bin/env python3
import csv,re,sqlite3,subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
R=Path('./22_Lab/06_Logs/fulltext_kb')
a=list(csv.DictReader((R/'corpus_manifest.csv').open()))
c=sqlite3.connect('file:./ftkb/index.sqlite?mode=ro',uri=True)
s=dict(c.execute('select attachment,status from processed'))
missing=[x for x in a if s.get(x['attachment'])=='no_text']
def info(x):
 try:
  r=subprocess.run(['pdfinfo',x['pdf']],capture_output=True,text=True,timeout=15)
  m=re.search(r'(?m)^Pages:\s+(\d+)',r.stdout)
  return [x['source'],x['attachment'],x['pdf'],int(m.group(1)) if m else '',r.returncode]
 except subprocess.TimeoutExpired:return [x['source'],x['attachment'],x['pdf'],'','timeout']
with ThreadPoolExecutor(max_workers=8) as ex:rows=list(ex.map(info,missing))
with (R/'no_text_pdf_page_counts.csv').open('x',newline='') as f:
 w=csv.writer(f);w.writerow(['source','attachment','pdf','physical_pages','pdfinfo_status']);w.writerows(rows)
print('no_text_files',len(rows),'pdfinfo_pages_known',sum(isinstance(x[3],int) for x in rows),'pages',sum(x[3] for x in rows if isinstance(x[3],int)))
