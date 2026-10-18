#!/usr/bin/env python3
"""Attempt non-destructive pypdf repair of stage1 failures, local desktop only."""
import hashlib, json, os, sqlite3, subprocess, sys, time
from pathlib import Path
sys.path.insert(0,str(Path.home()/'ftkb_ocr/vendor'))
from pypdf import PdfReader, PdfWriter
root=Path.home()/'ftkb_ocr'; out=root/'repaired';out.mkdir(exist_ok=True)
rows=[json.loads(x) for x in (root/'stage1_failures.jsonl').read_text().splitlines()]
seen=set();db=sqlite3.connect(root/'repaired_pages.sqlite',timeout=90)
db.execute('create table if not exists documents(sha256 text primary key, aliases_json text not null)')
db.execute('create table if not exists pages(sha256 text not null,physical_page integer not null,chars integer not null,has_text integer not null,origin text not null,text text,primary key(sha256,physical_page))')
for row in rows:
 path=row['path']
 if path in seen:continue
 seen.add(path)
 if path.endswith('/ICWE14_ID02130.pdf') or path.endswith('/dissecting MFC 2e part5.pdf'):continue
 try:
  sha=row['sha256'] or hashlib.sha256(Path(path).read_bytes()).hexdigest()
  reader=PdfReader(path,strict=False); n=len(reader.pages)
  writer=PdfWriter()
  for page in reader.pages:writer.add_page(page)
  repaired=out/(sha+'.pdf')
  with open(repaired,'wb') as stream:writer.write(stream)
  info=subprocess.run(['pdfinfo',str(repaired)],capture_output=True,text=True,timeout=120)
  if info.returncode:raise RuntimeError('repaired_pdfinfo:'+info.stderr[-200:])
  db.execute('insert or ignore into documents values(?,?)',(sha,json.dumps([{'wsl':path,'windows':path.replace('./','I:\\').replace('/','\\')}],ensure_ascii=False)))
  good=0;bad=[]
  for i in range(1,n+1):
   a=subprocess.run(['pdftotext','-f',str(i),'-l',str(i),'-layout',str(repaired),'-'],capture_output=True,timeout=90)
   if a.returncode:bad.append(i);continue
   text=a.stdout.decode('utf8','replace').strip(); good+=1
   db.execute('insert or replace into pages values(?,?,?,?,?,?)',(sha,i,len(text),int(bool(text)),'text_layer_repair',text if text else None))
   if i%50==0:db.commit()
  db.commit()
  print(json.dumps({'path':path,'sha256':sha,'reader_pages':n,'repaired_size':repaired.stat().st_size,'extracted_pages':good,'failed_pages':bad[:30],'failed_count':len(bad)},ensure_ascii=False),flush=True)
 except Exception as e:
  print(json.dumps({'path':path,'error':repr(e)},ensure_ascii=False),flush=True)
db.close()
