#!/usr/bin/env python3
"""Re-render only v2 fallback rows into a new v3 DB/root, preserving v2."""
import argparse,json,sqlite3
from pathlib import Path
import pymupdf as fitz
from figure_pipeline_v3 import CAP,PANEL_PREFIX,PREDICATE,NARRATIVE_VERB,region_above,render,VERSION
p=argparse.ArgumentParser();p.add_argument('--source-db',required=True);p.add_argument('--out-db',required=True);p.add_argument('--root',required=True);p.add_argument('--metadata',default=str(Path.home()/'ftkb_text/pdf_meta.jsonl'));p.add_argument('--manifest',help='staged PDF JSONL manifest');p.add_argument('--library',choices=['Desktop','Zotero','EndNote']);a=p.parse_args()
out=Path(a.out_db)
if out.exists():raise FileExistsError(out)
out.parent.mkdir(parents=True,exist_ok=True)
src=sqlite3.connect('file:'+a.source_db+'?mode=ro',uri=True);db=sqlite3.connect(str(out));src.backup(db);src.close()
paths={}
if a.library=='Desktop':
    for line in open(a.metadata):
        x=json.loads(line)
        if x.get('sha256') and x.get('path'):paths[x['sha256']]=x['path']
else:
    for line in open(a.manifest):
        x=json.loads(line)
        if x['library']==a.library:paths[x['attachment']]=x['staged_path']
rows=db.execute("SELECT fig_id,doc_id,physical_page,caption_text,caption_bbox,kind,thumb_path FROM figures WHERE kind IN ('vector','page_region') AND caption_text IS NOT NULL AND source_library=? ORDER BY doc_id,physical_page",(a.library,)).fetchall()
count=0;changed=0;rejected=0;missing=0;errors=[];current=None;pdf=None;page=None
for fid,doc,page_no,text,bbox,kind,thumb in rows:
    path=paths.get(doc)
    if not path or not Path(path).is_file():missing+=1;continue
    try:
        if current!=doc:
            if pdf:pdf.close()
            pdf=fitz.open(path);current=doc;loaded=None
        if loaded!=page_no:page=pdf.load_page(page_no-1);loaded=page_no
        m=CAP.match(text);tail=PANEL_PREFIX.sub('',text[m.end():].strip()) if m else ''
        panel=bool(PANEL_PREFIX.match(text[m.end():].strip())) if m else False
        if not tail or PREDICATE.match(tail) or (panel and NARRATIVE_VERB.search(' '.join(tail.split()[:8]))):
            db.execute('DELETE FROM figures WHERE fig_id=?',(fid,));rejected+=1;continue
        cb=fitz.Rect(json.loads(bbox))
        capboxes=[fitz.Rect(json.loads(x[0])) for x in db.execute('SELECT caption_bbox FROM figures WHERE source_library=? AND doc_id=? AND physical_page=? AND caption_bbox IS NOT NULL',(a.library,doc,page_no))]
        clip=region_above(page,cb,capboxes)
        newkind='vector' if clip is not None and clip.height>=65 else 'page_region'
        # Keep image_bbox NULL for fallback; clipping is the visible rendered region.
        dest=Path(a.root)/'thumbs'/thumb
        _,actual=render(page,None,cb,newkind,dest,capboxes)
        db.execute('UPDATE figures SET kind=?,extractor_version=? WHERE fig_id=?',(newkind,VERSION,fid))
        count+=1;changed+=int(newkind!=kind)
    except Exception as e:errors.append((fid,str(e)[:120]))
if pdf:pdf.close()
db.commit();db.close()
print(json.dumps(dict(library=a.library,candidates=len(rows),rerendered=count,kind_changed=changed,rejected_predicate=rejected,missing_pdf=missing,errors=errors[:20],error_count=len(errors)),ensure_ascii=False))
