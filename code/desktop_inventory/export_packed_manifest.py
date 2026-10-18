#!/usr/bin/env python3
"""Produce page-level manifest for SQLite-packed stage1+stage2 corpus."""
import json, sqlite3, os
from pathlib import Path
root=Path('./ftkb_desktop'); db=root/'page_text.sqlite'
con=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
out=root/'page_manifest_packed.jsonl';tmp=root/'page_manifest_packed.jsonl.partial'
with tmp.open('w',encoding='utf8') as f:
 for h,p,chars,present,origin,aliases in con.execute('select p.sha256,p.physical_page,p.chars,p.has_text,p.origin,d.aliases_json from pages p join documents d on p.sha256=d.sha256 order by p.sha256,p.physical_page'):
  row={'sha256':h,'aliases':json.loads(aliases),'page':p,'physical_page':p,'chars':chars,'has_text':bool(present),'text_path':f'sqlite://{db}#pages/{h}/{p}' if present else None,'origin':origin,'db_path':str(db)}
  f.write(json.dumps(row,ensure_ascii=False)+'\n')
os.replace(tmp,out)
print('packed manifest:',out, 'bytes:',out.stat().st_size)
