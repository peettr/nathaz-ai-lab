#!/usr/bin/env python3
"""Read-only Zotero PDF physical-page index/search. Index resides on WSL ext4."""
import argparse, json, os, re, sqlite3, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
DB = Path('./ftkb/index.sqlite')
ZDB = Path('./ftkb/zotero.sqlite')
STORAGE = Path('./Zotero/storage')

def source_items():
    c=sqlite3.connect(f'file:{ZDB}?mode=ro',uri=True)
    q='''SELECT ai.key, pi.key, COALESCE(t.value,''), COALESCE(d.value,''), a.path, ty.typeName
    FROM itemAttachments a JOIN items ai ON ai.itemID=a.itemID
    LEFT JOIN items pi ON pi.itemID=a.parentItemID
    LEFT JOIN itemTypes ty ON ty.itemTypeID=pi.itemTypeID
    LEFT JOIN itemData it ON it.itemID=a.parentItemID AND it.fieldID=1
    LEFT JOIN itemDataValues t ON t.valueID=it.valueID
    LEFT JOIN itemData idate ON idate.itemID=a.parentItemID AND idate.fieldID=6
    LEFT JOIN itemDataValues d ON d.valueID=idate.valueID
    WHERE a.contentType='application/pdf' AND ty.typeName NOT IN ('book','bookSection')'''
    for ak,pk,title,year,path,typ in c.execute(q):
        if not path or not path.startswith('storage:'): continue
        p=STORAGE/ak/path[8:]
        if not p.is_file():
            matches=list((STORAGE/ak).glob('*.pdf')) if (STORAGE/ak).exists() else []
            if len(matches)!=1:continue
            p=matches[0]
        yield ak,pk or ak,title,re.search(r'\d{4}',year).group() if re.search(r'\d{4}',year) else '',str(p),typ

def init(c):
    c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA synchronous=NORMAL')
    c.executescript('''CREATE TABLE IF NOT EXISTS pages(id INTEGER PRIMARY KEY, attachment TEXT, key TEXT, title TEXT, year TEXT, type TEXT, page INTEGER, text TEXT, pdf TEXT, UNIQUE(attachment,page));
    CREATE VIRTUAL TABLE IF NOT EXISTS page_fts USING fts5(title,text,content='pages',content_rowid='id',tokenize='porter unicode61');
    CREATE TABLE IF NOT EXISTS processed(attachment TEXT PRIMARY KEY,status TEXT,pages INTEGER,elapsed REAL);''')

def extract(item):
    ak,key,title,year,pdf,typ=item
    try:
        r=subprocess.run(['pdftotext','-enc','UTF-8','-layout',pdf,'-'],capture_output=True,timeout=90)
        if r.returncode and not r.stdout:raise RuntimeError(r.stderr.decode(errors='replace')[:150])
        pages=r.stdout.decode('utf-8',errors='replace').split('\f')
        if not pages[-1].strip():pages.pop()
        return item,'ok',[(i,re.sub(r'\s+',' ',text).strip()) for i,text in enumerate(pages,1) if len(text.strip())>=40]
    except Exception as e:return item,'error:'+str(e)[:150],[]

def build(limit=None):
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB);init(c)
    done={r[0] for r in c.execute('SELECT attachment FROM processed')}
    items=[x for x in source_items() if x[0] not in done]
    if limit:items=items[:limit]
    print('remaining',len(items),'processed',len(done),flush=True)
    t=time.time()
    with ThreadPoolExecutor(max_workers=6) as pool:
      for n,(item,status,pages) in enumerate(pool.map(extract,items),1):
        ak,key,title,year,pdf,typ=item;count=0
        for i,text in pages:
            cur=c.execute('INSERT OR IGNORE INTO pages(attachment,key,title,year,type,page,text,pdf) VALUES (?,?,?,?,?,?,?,?)',(ak,key,title,year,typ,i,text,pdf))
            if cur.rowcount:c.execute('INSERT INTO page_fts(rowid,title,text) VALUES (?,?,?)',(cur.lastrowid,title,text));count+=1
        if not count and status=='ok':status='no_text'
        c.execute('INSERT OR IGNORE INTO processed VALUES (?,?,?,?)',(ak,status,count,time.time()-t));c.commit()
        if n%100==0:print('new',n,'/',len(items),'pages',c.execute('select count(*) from pages').fetchone()[0],'sec',round(time.time()-t),flush=True)
    print('done',len(items),'total',c.execute('select count(*) from processed').fetchone()[0],'indexed_pages',c.execute('select count(*) from pages').fetchone()[0],flush=True)

def search(query,n=5):
    c=sqlite3.connect(f'file:{DB}?mode=ro',uri=True);c.row_factory=sqlite3.Row
    tokens=[已隐去]'[\w]+',query,flags=re.UNICODE)
    if not tokens:[已隐去] []
    expr=' OR '.join('"'+x.replace('"','')+'"' for x in tokens)
    q='''SELECT p.*,bm25(page_fts,2.,1.) rank FROM page_fts JOIN pages p ON p.id=page_fts.rowid WHERE page_fts MATCH ? ORDER BY rank LIMIT ?'''
    return [dict(x) for x in c.execute(q,(expr,n))]

def main():
    a=argparse.ArgumentParser();s=a.add_subparsers(dest='cmd',required=True);b=s.add_parser('build');b.add_argument('--limit',type=int);q=s.add_parser('search');q.add_argument('query');q.add_argument('-n',type=int,default=5);args=a.parse_args()
    if args.cmd=='build':build(args.limit)
    else:
        for x in search(args.query,args.n):
            print(f"{x['title']} ({x['year']}) key={x['key']} p.{x['page']} score={x['rank']:.3f}\n  {x['text'][:350]}\n")
if __name__=='__main__':main()
