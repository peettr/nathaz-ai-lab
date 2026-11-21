#!/usr/bin/env python3
"""台式机 all-source full run; gated, resumable 8/12 workers, isolated v2 root."""
import argparse,csv,hashlib,json,os,random,sqlite3,subprocess,sys
from pathlib import Path
from figure_pipeline_v3 import desktop_manifest,staged_manifest,SCHEMA
BASE=Path.home()/'ftkb_figures';ROOT=BASE/'full_v2';S=BASE/'scripts_restart_20261016';PY=Path.home()/'ftkb_text/venv/bin/python'
def merged(shards,out,caption_only):
    if out.exists():raise FileExistsError(out)
    db=sqlite3.connect(out);db.executescript(SCHEMA)
    try:
        for path in shards:
            src=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True)
            with db:
                db.executemany('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)',src.execute('SELECT * FROM documents'))
                q='SELECT * FROM figures WHERE caption_text IS NOT NULL' if caption_only else 'SELECT * FROM figures'
                db.executemany('INSERT INTO figures VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',src.execute(q))
            src.close()
        db.execute('VACUUM');db.commit()
    finally:db.close()
def main():
    p=argparse.ArgumentParser();p.add_argument('--lead-go',action='store_true');p.add_argument('--workers',type=int);p.add_argument('--manifest',required=True);p.add_argument('--work-map',required=True);p.add_argument('--pair-seed',type=int);p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    if not a.lead_go:raise SystemExit('STOP: 0069 completion and explicit Lead full-run go required')
    if a.workers is None or not 1<=a.workers<=12:raise SystemExit('workers must be 1..12 (<=8 while OCR active)')
    if not a.prepare_only and a.pair_seed is None:raise SystemExit('Lead must supply --pair-seed')
    # Do not assume OCR stopped merely because the operator requested 12 workers.
    ocr=subprocess.run(['pgrep','-f','^python3 ./ftkb_ocr/run.py'],capture_output=True,text=True).returncode==0
    if ocr and a.workers>8:raise SystemExit('OCR still active: at most 8 workers')
    if not os.environ.get('TMPDIR','').startswith(str(BASE)+'/'):
        raise SystemExit('TMPDIR must be inside ~/ftkb_figures/')
    manifest=Path(a.manifest)
    staged=staged_manifest(manifest)
    works={(x['library'],x['attachment']):x['work'] for x in map(json.loads,open(a.work_map))}
    for x in staged:x['work']=works[(x['source_library'],x['doc_id'])]
    if len(staged)!=4676 or len({(x['source_library'],x['doc_id']) for x in staged})!=4676:raise RuntimeError('incomplete staged manifest')
    already=set()
    if ROOT.exists():
        for shard in ROOT.glob('worker_*.sqlite'):
            c=sqlite3.connect('file:'+str(shard)+'?mode=ro',uri=True)
            already.update(c.execute('SELECT source_library,doc_id FROM documents'))
            c.close()
    missing=[x['local_path'] for x in staged if not Path(x['local_path']).is_file() and (x['source_library'],x['doc_id']) not in already]
    if missing:raise FileNotFoundError(f'{len(missing)} unprocessed staged PDFs missing; first {missing[0]}')
    desktop=desktop_manifest(str(Path.home()/'ftkb_text/pdf_meta.jsonl'),str(Path.home()/'ftkb_text/page_manifest_v2.jsonl.gz'))
    if len(desktop)!=12491:raise RuntimeError(f'Desktop count mismatch: {len(desktop)}')
    if (ROOT/'figures_full.sqlite').exists() or (ROOT/'FULL_REPORT.md').exists():raise FileExistsError('full final exists, refusing overwrite')
    ROOT.mkdir(parents=True,exist_ok=True)
    batches=[[] for _ in range(a.workers)]
    for doc in desktop+staged:
        idx=int(hashlib.sha256((doc['source_library']+':'+doc['doc_id']).encode()).hexdigest(),16)%a.workers
        batches[idx].append(doc)
    for i,docs in enumerate(batches):
        f=ROOT/f'docs_{i:02d}.jsonl'
        payload=''.join(json.dumps(d,ensure_ascii=False)+'\n' for d in docs)
        if f.exists():
            if f.read_text()!=payload:raise RuntimeError('worker count or manifest changed; refusing shard overwrite')
        else:f.write_text(payload)
    if a.prepare_only:print('prepared',sum(map(len,batches)),'docs',len(batches),'shards; no extraction');return
    procs=[]
    for i in range(a.workers):
        log=open(ROOT/f'worker_{i:02d}.log','a')
        cmd=['nice','-n','10',str(PY),str(S/'figure_pipeline_v3.py'),'--source','desktop','--docs-jsonl',str(ROOT/f'docs_{i:02d}.jsonl'),'--root',str(ROOT),'--db',str(ROOT/f'worker_{i:02d}.sqlite'),'--all-figures']
        procs.append((subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT),log))
    codes=[]
    for proc,log in procs:codes.append(proc.wait());log.close()
    if any(codes):raise RuntimeError(f'worker failures: {codes}; resume with same --workers')
    shards=[ROOT/f'worker_{i:02d}.sqlite' for i in range(a.workers)]
    for f in shards:
        c=sqlite3.connect('file:'+str(f)+'?mode=ro',uri=True);n=c.execute('SELECT count(*) FROM documents').fetchone()[0];c.close()
        if n!=len(batches[int(f.stem.split('_')[-1])]):raise RuntimeError(f'incomplete shard {f}: {n}')
    # Both DBs are first created on spacious desktop; 工作站 transfer checks 200MB cap.
    merged(shards,ROOT/'figures_full.sqlite',False)
    merged(shards,ROOT/'figures_compact.sqlite',True)
    compact=ROOT/'figures_compact.sqlite'
    if compact.stat().st_size>=200_000_000:raise RuntimeError(f'compact DB exceeds 200MB: {compact.stat().st_size}; stop and report')
    subprocess.run(['nice','-n','10',str(Path.home()/'ftkb_figures/venv/bin/python'),str(S/'build_vectors_full_v2.py'),'--db',str(compact),'--out',str(ROOT/'vectors_full_v2')],env={**os.environ,'OPENBLAS_NUM_THREADS':'1','A1_MODEL_CACHE':str(Path.home()/'ftkb_figures/models')},stdin=subprocess.DEVNULL,check=True)
    vector_bytes=sum((ROOT/('vectors_full_v2'+x)).stat().st_size for x in ('.npy','.json'))
    if vector_bytes>300_000_000:raise RuntimeError('vectors exceed 300 MB; keep desktop only, report before 工作站 copy')
    c=sqlite3.connect('file:'+str(compact)+'?mode=ro',uri=True)
    candidates=c.execute("SELECT fig_id,source_library,physical_page,caption_text,thumb_path,kind FROM figures WHERE caption_text IS NOT NULL AND kind!='table' ORDER BY fig_id").fetchall()
    picked=random.Random(a.pair_seed).sample(candidates,50)
    pairs=ROOT/'pairs_50';pairs.mkdir(exist_ok=True)
    with open(ROOT/'pairs_50.csv','x',newline='') as f:
        w=csv.writer(f);w.writerow(('fig_id','source_library','physical_page','caption_text','thumb_path','kind'))
        w.writerows(picked)
    subprocess.run([str(Path.home()/'ftkb_figures/venv/bin/python'),str(S/'make_pairs_v2.py'),'--csv',str(ROOT/'pairs_50.csv'),'--thumbs',str(ROOT/'thumbs'),'--out',str(pairs)],stdin=subprocess.DEVNULL,check=True)
    stats=c.execute("SELECT source_library,count(*),sum(caption_text IS NOT NULL) FROM figures GROUP BY source_library").fetchall();c.close()
    (ROOT/'FULL_REPORT.md').write_text('# A1 full run (automatic draft; Lead must review)\n\n'+f'Documents: {len(desktop)+len(staged)}; compact SQLite bytes: {compact.stat().st_size}; vectors bytes: {vector_bytes}; pair seed: {a.pair_seed}.\n\nFigures by library (caption-only compact): {stats}.\n\nFiles: figures_full.sqlite (all), figures_compact.sqlite, vectors_full_v2.npy/json, pairs_50.csv, pairs_50/. Review pairing manually.\n')
    print('full complete',len(desktop)+len(staged),'compact bytes',compact.stat().st_size,'vector bytes',vector_bytes)
if __name__=='__main__':main()
