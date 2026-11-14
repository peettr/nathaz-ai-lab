#!/usr/bin/env python3
"""Produce new caption-only DB from a full source DB, with FTS external content."""
import argparse,os,sqlite3
from pathlib import Path
from figure_pipeline import SCHEMA
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);a=p.parse_args()
if Path(a.out).exists():raise FileExistsError(a.out)
s=sqlite3.connect('file:'+a.source+'?mode=ro',uri=True);d=sqlite3.connect(a.out);d.executescript(SCHEMA)
with d:
 d.executemany('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)',s.execute('SELECT * FROM documents'))
 d.executemany('INSERT INTO figures VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',s.execute('SELECT * FROM figures WHERE caption_text IS NOT NULL'))
d.execute('VACUUM');print(os.path.getsize(a.out),d.execute('select count(*) from figures').fetchone()[0])
