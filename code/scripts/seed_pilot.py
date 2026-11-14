#!/usr/bin/env python3
"""Seed new FTS-external DB from legacy pilot without rerendering existing thumbnails."""
import argparse,sqlite3
from pathlib import Path
from figure_pipeline import SCHEMA
p=argparse.ArgumentParser();p.add_argument('--pilot',required=True);p.add_argument('--full',required=True);p.add_argument('--caption-only',action='store_true');a=p.parse_args()
if Path(a.full).exists():raise FileExistsError(a.full)
s=sqlite3.connect('file:'+a.pilot+'?mode=ro',uri=True);d=sqlite3.connect(a.full);d.executescript(SCHEMA)
with d:
 d.executemany('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)',s.execute('SELECT * FROM documents'))
 q='SELECT * FROM figures WHERE caption_text IS NOT NULL' if a.caption_only else 'SELECT * FROM figures'
 d.executemany('INSERT INTO figures VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',s.execute(q))
print('seeded',d.execute('select count(*) from documents').fetchone()[0],d.execute('select count(*) from figures').fetchone()[0])
