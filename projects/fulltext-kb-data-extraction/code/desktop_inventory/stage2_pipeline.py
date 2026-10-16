#!/usr/bin/env python3
"""Local packed page text + read-only desktop OCR. Never modifies desktop or frozen indices."""
import argparse, collections, hashlib, json, os, queue, random, re, shlex, shutil, sqlite3, subprocess, threading, time, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
ROOT=Path('./ftkb_desktop'); DB=ROOT/'page_text.sqlite'; HERE=Path(__file__).resolve().parent
SOCKET='./.ssh/sockets/[邮箱]'
SSH=['ssh','-o',f'ControlPath={SOCKET}','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false','[邮箱]']
LIMIT=4*1024**3; MINFREE=40*1024**3

def space():
    free=shutil.disk_usage('./').free
    if free<MINFREE: raise RuntimeError(f'C free {free/2**30:.2f} GiB < 40 GiB')
    total=int(subprocess.check_output(['du','-sB1',str(ROOT)]).split()[0])
    if total>LIMIT:raise RuntimeError(f'output {total/2**30:.2f} GiB > 4 GiB')
    return free,total

def connect():
    con=sqlite3.connect(DB); con.execute('pragma journal_mode=DELETE'); con.execute('pragma synchronous=FULL')
    con.execute('create table if not exists documents(sha256 text primary key, aliases_json text not null)')
    con.execute('create table if not exists pages(sha256 text not null, physical_page integer not null, chars integer not null, has_text integer not null, origin text not null, text text, primary key(sha256,physical_page), foreign key(sha256) references documents(sha256))')
    return con

def read_raw(path):
    with open(path,'r',encoding='utf-8',newline='') as f:return f.read()

def pack():
    space(); con=connect(); n=0; start=time.monotonic()
    manifest=ROOT/'page_manifest.jsonl'
    for line in manifest.open():
        row=json.loads(line); h=row['sha256']; p=row['physical_page']; text=read_raw(row['text_path']) if row['has_text'] else None
        assert text is None or len(text)==row['chars'],(h,p)
        con.execute('insert or ignore into documents values (?,?)',(h,json.dumps(row['aliases'],ensure_ascii=False)))
        con.execute('insert or ignore into pages values (?,?,?,?,?,?)',(h,p,row['chars'],int(row['has_text']),'text_layer',text))
        n+=1
        if n%5000==0:
            con.commit(); free,total=space(); print(f'pack {n} pages, {total/2**20:.1f} MiB, free {free/2**30:.2f} GiB',flush=True)
    con.commit()
    count=con.execute("select count(*) from pages where origin='text_layer'").fetchone()[0]
    assert n==count,(n,count)
    # Random and boundary checks before deleting individual intermediate text files.
    rng=random.Random(20261014)
    targets=[1,n//2,n]+rng.sample(range(1,n+1),min(1000,n))
    indices=set(targets); verified=0
    for i,line in enumerate(manifest.open(),1):
        if i not in indices:continue
        row=json.loads(line); got=con.execute('select text,chars,origin from pages where sha256=? and physical_page=?',(row['sha256'],row['physical_page'])).fetchone()
        want=read_raw(row['text_path']) if row['has_text'] else None
        assert got==(want,row['chars'],'text_layer'),(i,row['sha256']); verified+=1
    assert verified==len(indices)
    con.close()
    # Remove only self-produced stage1 intermediate page files, keeping original manifest untouched.
    shutil.rmtree(ROOT/'pages')
    free,total=space()
    print(json.dumps({'packed_pages':n,'verified_samples':verified,'seconds':time.monotonic()-start,'bytes':total,'C_free_bytes':free}),flush=True)

def priority(path):
    if path.startswith('./Book/'):
        name=path[len('./Book/'):].split('/')[0]
        ordered=['中文','wind engineering','Codes','Probability and Stochastic Vibration','Vibration and Structural Dynamics','CFD']
        return (0,ordered.index(name) if name in ordered else len(ordered))
    return (1,0)

def inputs():
    docs=collections.defaultdict(list); aliases={}
    for line in (ROOT/'stage2_no_text_pages.jsonl').open():
        x=json.loads(line); h=x['sha256']; docs[h].append(x['physical_page']);aliases[h]=x['aliases']
    sorted_docs=sorted(docs,key=lambda h:(priority(aliases[h][0]['wsl']),aliases[h][0]['wsl']))
    return [(h,aliases[h],sorted(docs[h])) for h in sorted_docs]

def ocr_one(pdf,page,lang):
    t=time.monotonic()
    render=subprocess.run(['nice','-n','19','ionice','-c3','pdftoppm','-f',str(page),'-l',str(page),'-scale-to','1500','-gray','-singlefile','-png',str(pdf)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if render.returncode or not render.stdout:raise RuntimeError(f'render {render.returncode}: {render.stderr[-180:]!r}')
    recognized=subprocess.run(['nice','-n','19','ionice','-c3','tesseract','stdin','stdout','-l',lang],input=render.stdout,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120,env={**os.environ,'OMP_THREAD_LIMIT':'1'})
    if recognized.returncode:raise RuntimeError(f'tess {recognized.returncode}: {recognized.stderr[-180:]!r}')
    text=recognized.stdout.decode('utf-8','replace').strip()
    return text,time.monotonic()-t

def fetch(h,aliases):
    path=aliases[0]['wsl']; dst=ROOT/'tmp'/f'{h}.pdf'; dst.parent.mkdir(exist_ok=True)
    cmd='nice -n 19 ionice -c3 cat -- '+shlex.quote(path)
    digest=hashlib.sha256()
    proc=subprocess.Popen(SSH+[cmd],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    with dst.open('wb') as f:
        while chunk:=proc.stdout.read(1024*1024):
            digest.update(chunk);f.write(chunk)
    err=proc.stderr.read(); rc=proc.wait(timeout=120)
    if rc or digest.hexdigest()!=h:
        dst.unlink(missing_ok=True)
        raise RuntimeError(f'fetch rc={rc} sha={digest.hexdigest()} expected={h}: {err[-180:]!r}')
    return dst

def run_ocr(workers=6):
    check=subprocess.run(['ssh','-O','check','-o',f'ControlPath={SOCKET}','x'],capture_output=True)
    if check.returncode:raise RuntimeError('existing SSH master missing; refusing reconnection')
    space(); con=connect(); docs=inputs(); start=time.monotonic(); processed=0; text_n=0; empty=0; failed=0; seconds=0; count_docs=0
    fail_log=(ROOT/'stage2_failures.jsonl').open('a'); stop=threading.Event()
    def heartbeat():
        while not stop.wait(60):
            print(f'OCR heartbeat elapsed={time.monotonic()-start:.0f}s docs_this_run={count_docs} pages_this_run={processed} text={text_n} empty={empty} failed={failed}',flush=True)
    threading.Thread(target=heartbeat,daemon=True).start()
    try:
        for h,aliases,pages in docs:
            existing={r[0] for r in con.execute("select physical_page from pages where sha256=? and origin='OCR 文本'",(h,))}
            todo=[p for p in pages if p not in existing]
            if not todo:continue
            free,total=space()
            dst=None
            try:
                dst=fetch(h,aliases); space()
                lang='chi_sim+eng' if re.search('[\u3400-\u9fff]',aliases[0]['wsl']) else 'eng+chi_sim'
                con.execute('insert or ignore into documents values (?,?)',(h,json.dumps(aliases,ensure_ascii=False)))
                # Bounded parallel page rendering; a per-document transaction ensures recoverable checkpoints.
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures={pool.submit(ocr_one,dst,p,lang):p for p in todo}
                    for fut in as_completed(futures):
                        p=futures[fut]
                        try:
                            text,sec=fut.result()
                            present=bool(re.search(r'[\w\u3400-\u9fff]',text))
                            con.execute('insert or replace into pages values (?,?,?,?,?,?)',(h,p,len(text) if present else 0,int(present),'OCR 文本',text if present else None))
                            processed+=1;seconds+=sec;text_n+=int(present);empty+=int(not present)
                            if processed%100==0:con.commit()
                        except Exception as e:
                            failed+=1;fail_log.write(json.dumps({'sha256':h,'page':p,'error':str(e)},ensure_ascii=False)+'\n');fail_log.flush()
                con.commit();count_docs+=1
            except Exception as e:
                con.commit(); failed+=len(todo);fail_log.write(json.dumps({'sha256':h,'pages':len(todo),'error':str(e)},ensure_ascii=False)+'\n');fail_log.flush()
            finally:
                if dst: dst.unlink(missing_ok=True)
            free,total=space()
            print(f'doc {count_docs} sha={h[:8]} pages_this_run={processed} empty={empty} failed={failed} time={time.monotonic()-start:.1f}s size_MiB={total/2**20:.1f} C_free_GiB={free/2**30:.2f}',flush=True)
    finally:
        stop.set(); con.commit();con.close();fail_log.close()
    free,total=space();print(json.dumps({'pages_this_run':processed,'text_pages_this_run':text_n,'empty_pages_this_run':empty,'failed_this_run':failed,'doc_this_run':count_docs,'ocr_cpu_seconds':seconds,'wall_seconds':time.monotonic()-start,'bytes':total,'C_free_bytes':free}),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['pack','ocr']);ap.add_argument('--workers',type=int,default=6);args=ap.parse_args()
    if args.mode=='pack':pack()
    else:run_ocr(args.workers)
