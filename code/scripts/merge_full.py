#!/usr/bin/env python3
"""Merge Desktop/local full databases into a new compact 工作站 figure-caption DB."""
import argparse,os,sqlite3
from pathlib import Path
from figure_pipeline import SCHEMA
p=argparse.ArgumentParser();p.add_argument('--desktop',required=True);p.add_argument('--local',required=True);p.add_argument('--out',required=True);a=p.parse_args()
if Path(a.out).exists():raise FileExistsError('refusing overwrite: '+a.out)
d=sqlite3.connect(a.out);d.executescript(SCHEMA)
for path in [a.desktop,a.local]:
 s=sqlite3.connect('file:'+path+'?mode=ro',uri=True)
 with d:
  d.executemany('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)',s.execute('SELECT * FROM documents'))
  d.executemany('INSERT INTO figures VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',s.execute('SELECT * FROM figures WHERE caption_text IS NOT NULL'))
 s.close()
d.execute('VACUUM')
print('documents',d.execute('SELECT count(*) FROM documents').fetchone()[0],'captioned figures',d.execute('SELECT count(*) FROM figures').fetchone()[0],'bytes',os.path.getsize(a.out))
if os.path.getsize(a.out)>=200_000_000:raise RuntimeError('SQLite exceeds 200 MB: omit image_bbox/caption_bbox or compress captions; keep result for inspection')
