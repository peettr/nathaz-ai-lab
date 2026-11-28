#!/usr/bin/env python3
"""Combine two immutable pilot databases, report metrics, freeze random pair manifest."""
import argparse,csv,json,os,random,sqlite3,statistics
from pathlib import Path
from figure_pipeline import SCHEMA

def main():
    a=argparse.ArgumentParser();a.add_argument('--desktop',required=True);a.add_argument('--local',required=True);a.add_argument('--out',required=True);a.add_argument('--pairs',required=True);a=a.parse_args()
    if Path(a.out).exists():raise FileExistsError(a.out)
    c=sqlite3.connect(a.out);c.executescript(SCHEMA)
    for name,p in [('desk',a.desktop),('loc',a.local)]:
        c.execute(f'ATTACH DATABASE ? AS {name}',(p,))
        with c:
            c.execute(f'INSERT INTO documents SELECT * FROM {name}.documents')
            c.execute(f'INSERT INTO figures SELECT * FROM {name}.figures')
            c.execute(f'INSERT INTO captions_fts SELECT * FROM {name}.captions_fts')
        c.execute(f'DETACH DATABASE {name}')
    c.commit();c.close()
    c=sqlite3.connect(a.out)
    rows=c.execute('SELECT source_library,doc_id,elapsed,status,n_pages,figures,captioned,vector_fallback,thumb_bytes FROM documents').fetchall()
    figs=c.execute('SELECT fig_id,source_library,physical_page,caption_text,thumb_path,kind,image_bbox FROM figures WHERE caption_text IS NOT NULL ORDER BY fig_id').fetchall()
    rng=random.Random(20261015);selected=rng.sample(figs,min(50,len(figs)))
    Path(a.pairs).parent.mkdir(parents=True,exist_ok=True)
    with open(a.pairs,'w',newline='') as f:
        w=csv.writer(f);w.writerow(['fig_id','source_library','physical_page','caption_text','thumb_path','kind','image_bbox'])
        w.writerows(selected)
    print(json.dumps({'documents':len(rows),'figures':len(c.execute('select fig_id from figures').fetchall()),'captions':len(figs),'errors':{s:sum(r[3]==s for r in rows) for s in set(r[3] for r in rows) if s!='ok'},'by_library':{l:{'documents':len(sub),'figures':sum(r[5] for r in sub),'captioned':sum(r[6] for r in sub),'vector_fallback':sum(r[7] for r in sub),'thumb_bytes':sum(r[8] for r in sub),'elapsed':sum(r[2] for r in sub),'median_elapsed':statistics.median(r[2] for r in sub)} for l in set(r[0] for r in rows) for sub in [[r for r in rows if r[0]==l]]},'sqlite_bytes':os.path.getsize(a.out)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
