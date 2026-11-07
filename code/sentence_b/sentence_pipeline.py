#!/usr/bin/env python3
"""Read-only page snapshot -> resumable per-1000-page sentence/embedding shards.
Run ONLY on desktop; write ONLY ~/ftkb_sentences. No network model downloads.
"""
import argparse, json, os, re, sqlite3, sys, time
from pathlib import Path
import numpy as np
from fastembed import TextEmbedding

ROOT=Path.home()/'ftkb_sentences'
MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
CACHE=str(Path.home()/'ftkb_figures/models') # existing model is read-only
BLOCK=1000
SPLIT=re.compile(r'(?<=[.!?。！？])\s+(?=[A-Z\d“"(\[\u4e00-\u9fff])|(?<=[。！？])(?=[\u4e00-\u9fff])')
REF=re.compile(r'^(?:\s*(?:references|bibliography|works cited|参考文献)\s*$)',re.I)
LINE_NOISE=re.compile(r'^\s*(?:fig(?:ure)?\.?|table|图|表)\s*[\d一二三四五六七八九十]+\b|(?:\.{3,}|…{2,}|·{3,})\s*\d+\s*$|^\s*(?:\d+|[ivxlcdm]+)\s*$',re.I)
CJK=re.compile(r'[\u4e00-\u9fff]')
WORDS=re.compile(r"\b[\w]+(?:[-’'][\w]+)*\b")

def sentences(text):
    # PDF text has arbitrary hard wraps; retain blank-line paragraph breaks.
    text=text.replace('\x00',' ').replace('\u00ad','').replace('\r','\n')
    paragraphs=[]; lines=[]; in_refs=False
    for raw in text.split('\n'):
        line=raw.strip()
        if REF.fullmatch(line): in_refs=True; break
        if not line:
            if lines: paragraphs.append(' '.join(lines));lines=[]
            continue
        if LINE_NOISE.search(line): continue
        # short isolated all-caps / running heads / page numbers; imperfect without geometry
        if len(line)<12 and (line.isupper() or line.isdigit()): continue
        lines.append(line)
    if lines: paragraphs.append(' '.join(lines))
    for para in paragraphs:
        para=re.sub(r'(?<=\w)-\s+(?=\w)','',para)
        for raw in SPLIT.split(para):
            s=' '.join(raw.split()).strip(' ·•–-')
            if not s or LINE_NOISE.match(s):continue
            chinese=len(CJK.findall(s)); n=len(WORDS.findall(s))
            units=n+chinese/2
            if 8<=units<=80 and len(s)<=800 and len(s)>=30:
                yield s

def model():
    return TextEmbedding(model_name=MODEL,cache_dir=CACHE,threads=6,local_files_only=True)

def build():
    root=ROOT; out=root/'shards';out.mkdir(parents=True,exist_ok=True)
    inp=sqlite3.connect(f'file:{root}/input/index.sqlite?mode=ro',uri=True)
    inp.row_factory=sqlite3.Row
    maxid=inp.execute('select max(id) from pages').fetchone()[0]
    embed=model();begin=time.monotonic();done=0
    for start in range(1,maxid+1,BLOCK):
        tag=f'{start:07d}'; db=out/(tag+'.sqlite'); vec=out/(tag+'.i8'); meta=out/(tag+'.json')
        if meta.exists() and db.exists() and vec.exists():
            done+=1;continue
        rows=inp.execute('''SELECT p.id,p.attachment,p.work,p.title,p.year,p.page,p.text,p.text_source,
                   a.library FROM pages p LEFT JOIN attachments a ON p.attachment=a.attachment
                   WHERE p.id>=? AND p.id<? ORDER BY p.id''',(start,start+BLOCK)).fetchall()
        if not rows:continue
        records=[]; nocr=0
        for p in rows:
            if p['text_source']=='ocr':nocr+=1
            for j,s in enumerate(sentences(p['text'] or ''),1):
                records.append((p['id'],p['work'],p['attachment'],p['title'],p['year'],p['page'],j,int(p['text_source']=='ocr'),p['library'],s))
        tmpdb=out/(tag+'.sqlite.part');tmpvec=out/(tag+'.i8.part')
        for f in (tmpdb,tmpvec):
            if f.exists():f.unlink()  # only this incomplete shard; never existing completed result
        c=sqlite3.connect(tmpdb)
        c.execute('create table sentences (sid integer primary key,page_id integer,work text,attachment text,title text,year text,physical_page integer,sentence_no integer,is_ocr integer,library text,text text)')
        c.executemany('insert into sentences(page_id,work,attachment,title,year,physical_page,sentence_no,is_ocr,library,text) values(?,?,?,?,?,?,?,?,?,?)',records)
        c.commit();c.close()
        with open(tmpvec,'wb') as f:
            for base in range(0,len(records),256):
                batch=[r[-1] for r in records[base:base+256]]
                for v in embed.embed(batch,batch_size=64):
                    v=np.asarray(v,dtype=np.float32)
                    v/=max(float(np.linalg.norm(v)),1.e-12)
                    f.write(np.clip(np.rint(v*127),-127,127).astype(np.int8).tobytes())
        size=tmpvec.stat().st_size; n=len(records)
        if n and size != n*384:raise RuntimeError(f'shard {tag} vectors {size} != {n}*384')
        os.replace(tmpdb,db);os.replace(tmpvec,vec)
        meta.write_text(json.dumps(dict(start=start,pages=len(rows),ocr_pages=nocr,sentences=n,seconds=round(time.monotonic()-begin,1),vector_bytes=size),ensure_ascii=False)+'\n')
        done+=1
        print(f'{time.strftime("%m-%d %H:%M:%S")} shard={tag} pages={len(rows)} sentences={n} completed={done} elapsed_s={time.monotonic()-begin:.0f}',flush=True)
    print('DONE',done,'seconds',time.monotonic()-begin,flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['build']:build()
    elif sys.argv[1:]==['test']:
        for s in sentences('Figure 2. Wind speeds. Climate change is expected to decrease mean wind speed in many regions.\n\n雷暴风与非雷暴风应分开拟合，否则长重现期设计风速可能产生偏差。'):print(s)
    else:raise SystemExit('usage: sentence_pipeline.py build|test')
