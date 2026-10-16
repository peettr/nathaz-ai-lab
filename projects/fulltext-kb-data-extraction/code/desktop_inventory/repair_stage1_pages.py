#!/usr/bin/env python3
"""Conservative per-page repair of the two stage1 boundary-mismatch PDFs."""
import json,re,shlex,sqlite3,subprocess,time,hashlib
from pathlib import Path
ROOT=Path('./ftkb_desktop'); HERE=Path(__file__).resolve().parent
SSH=['ssh','-o','ControlPath=./.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false','[邮箱]']
fail={x['path']:x for line in (ROOT/'stage1_failures.jsonl').open() if (x:=json.loads(line)).get('path')}
page_counts={'ICWE14_ID02130.pdf':10,'dissecting MFC 2e part5.pdf':105}
con=sqlite3.connect(ROOT/'page_text.sqlite');con.execute('pragma journal_mode=DELETE')
for path,x in fail.items():
 if not ('ICWE14_ID02130.pdf' in path or 'dissecting MFC 2e part5.pdf' in path):continue
 n=next(v for k,v in page_counts.items() if k in path); t=time.monotonic()
 cmd='nice -n 19 ionice -c3 sha256sum -- '+shlex.quote(path)
 r=subprocess.run(SSH+[cmd],capture_output=True,text=True,timeout=90)
 if r.returncode:raise RuntimeError((path,r.stderr))
 h=r.stdout[:64];assert re.fullmatch('[0-9a-f]{64}',h)
 aliases=[{'wsl':path,'windows':'I:\\'+path[len('./'):].replace('/','\\')}]
 count=0;nonzero=0;problem=[]
 for page in range(1,n+1):
  cmd='nice -n 19 ionice -c3 pdftotext -layout -enc UTF-8 -f '+str(page)+' -l '+str(page)+' '+shlex.quote(path)+' -'
  out=subprocess.run(SSH+[cmd],capture_output=True,timeout=90)
  # Output of exactly one physical page; FFs inside page are kept as page content.
  body=out.stdout.decode('utf-8','replace').strip()
  if out.returncode or (not body and b'Failed to parse XRef' in out.stderr):
   problem.append(page);continue
  has=bool(re.search(r'[\w\u3400-\u9fff]',body));nonzero+=int(has)
  con.execute('insert or ignore into documents values (?,?)',(h,json.dumps(aliases,ensure_ascii=False)))
  con.execute('insert or replace into pages values (?,?,?,?,?,?)',(h,page,len(body) if has else 0,int(has),'text_layer_repair',body if has else None))
  count+=1
 con.commit();print(json.dumps({'path':path,'sha256':h,'pages':n,'mapped':count,'text_pages':nonzero,'unreadable':problem,'seconds':round(time.monotonic()-t,1)},ensure_ascii=False),flush=True)
con.close()
