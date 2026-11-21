#!/usr/bin/env python3
"""Read-only inventory -> Zotero PDF path mapping for local inspection."""
import csv,sqlite3,json,re
from pathlib import Path
BASE=Path(__file__).parent
r=list(csv.DictReader(open(BASE/'inventory.csv',encoding='utf-8-sig')))
z=sqlite3.connect('file:./Zotero/zotero.sqlite?mode=ro',uri=True)
z.row_factory=sqlite3.Row
for rec in r:
 paths=[]
 for key in rec['library_item_ids'].split(';'):
  for a in z.execute('select i.key,ia.path from items p join itemAttachments ia on ia.parentItemID=p.itemID join items i on i.itemID=ia.itemID where p.key=? and ia.contentType=?',(key,'application/pdf')):
   path=a['path'] or ''
   if path.startswith('storage:'):path='./Zotero/storage/'+a['key']+'/'+path[8:]
   if Path(path).is_file():paths.append(path)
 if paths: print(json.dumps({'id':rec['work_id'],'title':rec['title'],'topic':rec['topic'],'author':rec['authors'],'paths':paths},ensure_ascii=False))
