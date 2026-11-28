#!/usr/bin/env python3
"""Bounded figure/caption extraction; one document per transaction; no source mutation."""
import argparse, csv, gzip, hashlib, json, os, random, re, sqlite3, time
from pathlib import Path
import pymupdf as fitz

VERSION='a1-pilot-4'
CAP=re.compile(r'^\s*((?:Fig(?:ure)?\.?|图|表|Table)\s*(?:S?\d+[A-Za-z]?(?:[.\-–]\d+)?|[IVX]+)\s*[.:：\-–]?\s*)',re.I)
TABLE=re.compile(r'^\s*(?:Table\b|表)',re.I)
PREDICATE=re.compile(r'^(?:shows?|showed|shown|gives?|gave|given|presents?|presented|illustrates?|illustrated|depicts?|depicted|demonstrates?|demonstrated|indicates?|indicated|compares?|compared|contains?|contained|provides?|provided|displays?|displayed|represents?|represented|experiences?|experienced|is|are|was|were|can|may)\b',re.I)
PANEL_PREFIX=re.compile(r'^\s*\([a-z](?:\s*[-–]\s*[a-z])?\)\s*[.:]?\s*',re.I)
NARRATIVE_VERB=re.compile(r'\b(?:experienced|showed|indicated|demonstrated|compared|presented|illustrated|depicted)\b',re.I)
DOT_LEADER=re.compile(r'(?:\.{3,}|…{2,}|·{3,}|_{3,})\s*\d+\s*$')
SCHEMA='''CREATE TABLE IF NOT EXISTS documents(source_library TEXT NOT NULL,doc_id TEXT NOT NULL,work TEXT,pdf_path TEXT,elapsed REAL DEFAULT 0,status TEXT,n_pages INTEGER DEFAULT 0,figures INTEGER DEFAULT 0,captioned INTEGER DEFAULT 0,vector_fallback INTEGER DEFAULT 0,thumb_bytes INTEGER DEFAULT 0,PRIMARY KEY(source_library,doc_id));
CREATE TABLE IF NOT EXISTS figures(fig_id TEXT PRIMARY KEY,source_library TEXT NOT NULL,doc_id TEXT NOT NULL,work TEXT,pdf_path TEXT,physical_page INTEGER,fig_label TEXT,caption_text TEXT,caption_bbox TEXT,image_bbox TEXT,kind TEXT,thumb_path TEXT,extractor_version TEXT);
CREATE INDEX IF NOT EXISTS fig_doc ON figures(source_library,doc_id);
CREATE VIRTUAL TABLE IF NOT EXISTS captions_fts USING fts5(caption_text,content='figures',content_rowid='rowid', tokenize='unicode61');
CREATE TRIGGER IF NOT EXISTS figures_ai AFTER INSERT ON figures WHEN new.caption_text IS NOT NULL BEGIN INSERT INTO captions_fts(rowid,caption_text) VALUES(new.rowid,new.caption_text); END;
CREATE TRIGGER IF NOT EXISTS figures_ad AFTER DELETE ON figures WHEN old.caption_text IS NOT NULL BEGIN INSERT INTO captions_fts(captions_fts,rowid,caption_text) VALUES('delete',old.rowid,old.caption_text); END;'''

def db_open(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(path);c.executescript(SCHEMA);return c

def desktop_manifest(meta,manifest):
    origins={};aliases={}
    with gzip.open(manifest,'rt') as f:
        for line in f:
            x=json.loads(line); k=x['sha256']; p=x['physical_page']; origins.setdefault(k,{})[p]=x.get('origin','')
            if k not in aliases:aliases[k]=x.get('aliases') or []
    docs=[]
    with open(meta) as f:
        for line in f:
            x=json.loads(line);k=x.get('sha256'); path=x.get('path')
            if not k or not path:continue
            al=aliases.get(k,[]); win=next((a.get('windows') for a in al if a.get('wsl')==path),None)
            if not win:win='I:'+path[6:].replace('/','\\') if path.startswith('./') else path
            # Windows alias in source manifests sometimes contains doubled separators.
            win=re.sub(r'\\{2,}',r'\\',win)
            docs.append(dict(source_library='Desktop',doc_id=k,work=None,pdf_path=win,local_path=path,origins=origins.get(k,{})))
    return docs

def local_manifest(index):
    c=sqlite3.connect('file:'+index+'?mode=ro',uri=True)
    rows=c.execute("SELECT attachment,library,work,pdf FROM attachments WHERE library IN ('Zotero','EndNote') AND pdf IS NOT NULL").fetchall()
    c.close();return [dict(source_library=l,doc_id=a,work=w,pdf_path=p,local_path=p,origins={}) for a,l,w,p in rows]

def staged_manifest(path):
    return [dict(source_library=x['library'],doc_id=x['attachment'],work=x.get('work'),pdf_path=x['original_path'],local_path=x['staged_path'],origins={}) for x in (json.loads(line) for line in open(path))]

def sample(docs,seed,pilot):
    if not pilot:return docs
    r=random.Random(seed);out=[]
    for lib,n in [('Desktop',150),('Zotero',150),('EndNote',50)]:
        if not any(d['source_library']==lib for d in docs):continue
        group=[d for d in docs if d['source_library']==lib and os.path.isfile(d['local_path'])]
        if lib=='Desktop':
            lit=[d for d in group if '/Literature/' in d['local_path'] and any(v=='text_layer' for v in d['origins'].values())]
            book=[d for d in group if '/Book/' in d['local_path'] and any(v=='text_layer' for v in d['origins'].values())]
            if len(lit)<150 or len(book)<50:raise RuntimeError(f'Desktop eligible Literature={len(lit)} Book={len(book)}')
            out+=r.sample(sorted(lit,key=lambda x:x['doc_id']),150)+r.sample(sorted(book,key=lambda x:x['doc_id']),50)
        else:
            if len(group)<n:raise RuntimeError(f'{lib} eligible={len(group)}')
            out+=r.sample(sorted(group,key=lambda x:x['doc_id']),n)
    return out

def captions(page,allow=True):
    if not allow:return []
    blocks=sorted((b for b in page.get_text('blocks') if len(b)>6 and b[6]==0),key=lambda b:(round(b[1]/6),b[0]))
    lines=[(' '.join(b[4].split()),b) for b in blocks]
    headings=re.compile(r'^(?:contents|table of contents|list of (?:figures|tables)|illustrations|目录|图目录|插图目录|表目录)\s*$',re.I)
    if any(headings.match(t) for t,b in lines if b[1]<page.rect.height*.38) or sum(bool(DOT_LEADER.search(t)) for t,b in lines)>=3:return []
    out=[]
    for txt,b in lines:
        m=CAP.match(txt)
        if not m:continue
        tail=PANEL_PREFIX.sub('',txt[m.end():].strip())
        panel=bool(PANEL_PREFIX.match(txt[m.end():].strip()))
        if not tail or len(txt)>500 or b[3]-b[1]>78 or PREDICATE.match(tail) or (panel and NARRATIVE_VERB.search(' '.join(tail.split()[:8]))) or DOT_LEADER.search(txt):continue
        out.append((m.group(1).strip().rstrip('.:：-– '),txt,fitz.Rect(b[:4]),'table' if TABLE.match(txt) else 'figure'))
    return out

def candidates(page):
    rect=page.rect; imgs=[]
    for im in page.get_image_info(xrefs=True):
        b=fitz.Rect(im['bbox'])
        if b.width>=35 and b.height>=25 and b.get_area()>=rect.get_area()*.003 and rect.intersects(b):imgs.append(b)
    # Deduplicate overlapping raster xrefs.
    return [b for i,b in enumerate(imgs) if not any(b.intersect(a).get_area()/max(b.get_area(),1)>.8 for a in imgs[:i])]

def choose(caption,images,page):
    images=[b for b in images if b.get_area()<page.rect.get_area()*.70]
    if not images:return None,'page_region'
    cb=caption; above=[b for b in images if b.y1<=cb.y0+12]
    below=[b for b in images if b.y0>=cb.y1-12]
    pool=above or below or images
    def score(b):
        dy=max(0,cb.y0-b.y1) if b in above else max(0,b.y0-cb.y1) if b in below else abs((b.y0+b.y1-cb.y0-cb.y1)/2)
        dx=abs((b.x0+b.x1-cb.x0-cb.x1)/2)
        return dy+dx*.35
    best=min(pool,key=score)
    # A remote raster above a new caption often belongs to the preceding figure.
    if score(best)>page.rect.height*.20:return None,'page_region'
    return best,'raster'

def region_above(page,caption,all_captions):
    r=page.rect
    blocks=[fitz.Rect(b[:4]) for b in page.get_text('blocks') if len(b)>6 and b[6]==0]
    mid=(r.x0+r.x1)/2;twocol=any(b.x1<mid-15 for b in blocks) and any(b.x0>mid+15 for b in blocks)
    if twocol and caption.width<r.width*.66:
        left=caption.x0<mid;x0=r.x0+12 if left else mid+8;x1=mid-8 if left else r.x1-12
    else:x0=max(r.x0+8,caption.x0-45);x1=min(r.x1-8,caption.x1+45)
    # Only paragraph-sized, column-wide prose can terminate a figure region.
    # Axis numbers, legends, panel letters, and short annotations are inside it.
    column=x1-x0
    prose=[]
    for b in page.get_text('blocks'):
        if len(b)<=6 or b[6]!=0:continue
        box=fitz.Rect(b[:4]);text=' '.join(b[4].split())
        if box.y1>caption.y0-5 or box.x1<=x0 or box.x0>=x1:continue
        if CAP.match(text):continue
        if len(text)>=100 and box.width>=column*.55 and (box.height>=22 or len(text)>=160):prose.append(box.y1)
    prior=prose
    prior += [b.y1 for b in all_captions if b.y1<=caption.y0-5 and b.x1>x0 and b.x0<x1]
    y1=caption.y0-4;y0=max(r.y0+8,max(prior,default=r.y0)+4)
    clip=fitz.Rect(x0,y0,x1,y1)&r
    return clip if clip.height>=35 and clip.width>=55 else None

def render(page,box,caption,kind,out,all_captions=()):
    r=page.rect
    clip=(box&r) if box is not None else region_above(page,caption,all_captions)
    if clip is None:clip=fitz.Rect(max(r.x0,caption.x0-25),max(r.y0,caption.y0-100),min(r.x1,caption.x1+25),max(r.y0+10,caption.y0-5))
    if clip.is_empty or clip.height<10:raise ValueError('no drawable figure region')
    scale=min(1.4,512/max(clip.width,clip.height));pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=clip,alpha=False)
    Path(out).parent.mkdir(parents=True,exist_ok=True)
    data=pix.tobytes('jpeg',jpg_quality=80)
    with open(out,'wb') as f:f.write(data)
    return len(data),[round(x,2) for x in clip]

def process(c,doc,root,all_figures=False):
    lib=doc['source_library'];key=doc['doc_id'];path=doc['local_path'];start=time.monotonic();entries=[];stats=dict(figures=0,captioned=0,vector_fallback=0,thumb_bytes=0,n_pages=0,status='ok')
    errors={};filtered=0
    def err(e):
        name=type(e).__name__+': '+str(e)[:65];errors[name]=errors.get(name,0)+1
    try:
        pdf=fitz.open(path);stats['n_pages']=len(pdf)
        for i in range(len(pdf)):
            try:page=pdf.load_page(i)
            except Exception as e:err(e);continue
            allow=doc['origins'].get(i+1,'text_layer') not in ('OCR 文本','ocr','ocr_text')
            try:
                raw=page.get_text('blocks') if allow else []
                filtered+=sum(bool(CAP.match(' '.join(b[4].split()))) for b in raw if len(b)>6 and b[6]==0)
                caps=captions(page,allow);filtered-=len(caps)
            except Exception as e:err(e);caps=[]
            try:imgs=candidates(page)
            except Exception as e:err(e);imgs=[]
            for j,(label,text,cb,typ) in enumerate(caps,1):
                if typ=='table':continue
                box,kind=choose(cb,imgs,page)
                if box is None:
                    clip=region_above(page,cb,[x[2] for x in caps]);kind='vector' if clip is not None and clip.height>=65 else 'page_region'
                figid=hashlib.sha256(f'{lib}:{key}:{i+1}:{j}:{label}'.encode()).hexdigest()[:24]
                thumb=f'{lib}/{key}/p{i+1}_f{j}.jpg'
                try:size,clip=render(page,box,cb,kind,Path(root)/'thumbs'/thumb,[x[2] for x in caps])
                except Exception as e:err(e);continue
                entries.append((figid,lib,key,doc.get('work'),doc['pdf_path'],i+1,label,text,json.dumps([round(x,2) for x in cb]),json.dumps([round(x,2) for x in box]) if box else None,kind,thumb,VERSION))
                stats['figures']+=1;stats['captioned']+=1;stats['vector_fallback']+=int(box is None);stats['thumb_bytes']+=size
            # OCR/textless pages: extract raster picture without a caption; limit to meaningful areas.
            if not allow or not caps:
                for j,b in enumerate(imgs,1):
                    if b.get_area()<page.rect.get_area()*.04:continue
                    figid=hashlib.sha256(f'{lib}:{key}:{i+1}:uncap:{j}'.encode()).hexdigest()[:24]
                    thumb=f'{lib}/{key}/p{i+1}_f{len(caps)+j}.jpg'
                    try:size,_=render(page,b,b,'raster',Path(root)/'thumbs'/thumb)
                    except Exception as e:err(e);continue
                    entries.append((figid,lib,key,doc.get('work'),doc['pdf_path'],i+1,None,None,None,json.dumps([round(x,2) for x in b]),'raster',thumb,VERSION))
                    stats['figures']+=1;stats['thumb_bytes']+=size
        pdf.close()
    except Exception as e:err(e);stats['status']='fatal: '+type(e).__name__+': '+str(e)[:90]
    if errors and stats['status']=='ok':stats['status']='partial: '+json.dumps(errors,ensure_ascii=False)
    stats['decode_errors']=errors;stats['filtered_captions']=filtered
    stats['elapsed']=time.monotonic()-start
    with c:
        c.execute('DELETE FROM figures WHERE source_library=? AND doc_id=?',(lib,key))
        c.executemany('INSERT INTO figures VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',[x for x in entries if all_figures or x[7]])
        c.execute('INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)',(lib,key,doc.get('work'),doc['pdf_path'],stats['elapsed'],stats['status'],stats['n_pages'],stats['figures'],stats['captioned'],stats['vector_fallback'],stats['thumb_bytes']))
    return stats

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',choices=['desktop','local'],required=True);ap.add_argument('--root',required=True);ap.add_argument('--db',required=True);ap.add_argument('--pilot',action='store_true');ap.add_argument('--selection',help='JSONL of selected documents; generated if absent');ap.add_argument('--metadata',default=os.path.expanduser('~/ftkb_text/pdf_meta.jsonl'));ap.add_argument('--manifest',default=os.path.expanduser('~/ftkb_text/page_manifest_v2.jsonl.gz'));ap.add_argument('--index',default='./services/ftkb/data/index.sqlite');ap.add_argument('--staged-manifest');ap.add_argument('--docs-jsonl');ap.add_argument('--delete-staged-after',action='store_true');ap.add_argument('--seed',type=int,default=20261015);ap.add_argument('--limit',type=int);ap.add_argument('--all-figures',action='store_true');a=ap.parse_args()
    docs=[json.loads(line) for line in open(a.docs_jsonl)] if a.docs_jsonl else (desktop_manifest(a.metadata,a.manifest) if a.source=='desktop' else (staged_manifest(a.staged_manifest) if a.staged_manifest else local_manifest(a.index)))
    if a.selection and os.path.exists(a.selection):
        keys={(x['source_library'],x['doc_id']) for x in map(json.loads,open(a.selection))};docs=[d for d in docs if (d['source_library'],d['doc_id']) in keys]
    elif a.pilot:
        # Local mode has no desktop PDF access; sample 150 Zotero + 50 EndNote.
        if a.source=='local':docs=[d for d in docs if d['source_library'] in ('Zotero','EndNote')]
        docs=sample(docs,a.seed,True)
        if a.selection:
            Path(a.selection).parent.mkdir(parents=True,exist_ok=True)
            with open(a.selection,'w') as f:
                for d in docs:f.write(json.dumps({k:d[k] for k in ('source_library','doc_id')})+'\n')
    if a.limit:docs=docs[:a.limit]
    c=db_open(a.db);done=set(c.execute('SELECT source_library,doc_id FROM documents').fetchall())
    for n,d in enumerate(docs,1):
        if (d['source_library'],d['doc_id']) in done:continue
        s=process(c,d,a.root,a.all_figures)
        print(json.dumps({'n':n,'library':d['source_library'],'id':d['doc_id'],**s}),flush=True)
        if a.delete_staged_after and d['source_library']!='Desktop' and not s['status'].startswith('fatal'):
            staged=Path(d['local_path']).resolve();expected_ro=(Path.home()/'ftkb_figures/p14_pdfs').resolve()
            if not staged.is_relative_to(expected_ro):raise RuntimeError('refusing to delete non-staged PDF '+str(staged))
            staged.unlink(missing_ok=True)
    c.close()
if __name__=='__main__':main()
