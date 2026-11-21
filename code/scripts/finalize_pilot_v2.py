#!/usr/bin/env python3
"""Merge immutable source pilots, keep caption-only 工作站 DB, draw deterministic 50 pairs."""
import argparse,csv,random,sqlite3,os,json,collections,statistics
from pathlib import Path
from figure_pipeline_v2 import SCHEMA
p=argparse.ArgumentParser();p.add_argument('--desktop',required=True);p.add_argument('--local',required=True);p.add_argument('--out',required=True);p.add_argument('--pairs',required=True);a=p.parse_args()
if Path(a.out).exists() or Path(a.pairs).exists():raise FileExistsError('v2 output exists')
d=sqlite3.connect(a.out);d.executescript(SCHEMA)
for src in (a.desktop,a.local):
 s=sqlite3.connect('file:'+src+'?mode=ro',uri=True)
 with d:
  d.executemany('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)',s.execute('SELECT * FROM documents'))
  d.executemany('INSERT INTO figures VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',s.execute("SELECT * FROM figures WHERE caption_text IS NOT NULL AND kind!='table' AND caption_text NOT GLOB '表*' AND caption_text NOT LIKE 'Table %'"))
 s.close()
d.execute('VACUUM')
figs=d.execute("SELECT fig_id,source_library,physical_page,caption_text,thumb_path,kind,image_bbox FROM figures WHERE kind!='table' ORDER BY fig_id").fetchall()
rng=random.Random(20261016);chosen=rng.sample(figs,50)
with open(a.pairs,'w',newline='') as f:
 w=csv.writer(f);w.writerow(['fig_id','source_library','physical_page','caption_text','thumb_path','kind','image_bbox']);w.writerows(chosen)
rows=d.execute('SELECT source_library,elapsed,status,figures,captioned,vector_fallback,thumb_bytes FROM documents').fetchall()
print(json.dumps({'docs':len(rows),'caption_rows':len(figs),'sqlite_bytes':os.path.getsize(a.out),'figures':sum(r[3] for r in rows),'captioned':sum(r[4] for r in rows),'thumb_bytes':sum(r[6] for r in rows),'kind':dict(d.execute('SELECT kind,count(*) FROM figures GROUP BY kind')),'libraries':{lib:{'docs':len(rs),'figures':sum(r[3] for r in rs),'captioned':sum(r[4] for r in rs),'thumb_bytes':sum(r[6] for r in rs),'seconds':sum(r[1] for r in rs)} for lib in ('Desktop','Zotero','EndNote') for rs in [[r for r in rows if r[0]==lib]]},'status_counts':dict(collections.Counter(r[2].split(':')[0] for r in rows))},ensure_ascii=False,indent=2))
