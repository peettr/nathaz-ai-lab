#!/usr/bin/env python3
"""Desktop-local, resumable page OCR; sources are read-only."""
import argparse
import concurrent.futures as cf
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time

ROOT = Path.home() / 'ftkb_ocr'
TESS = Path.home() / 'ftkb_djvu/pkg/usr/bin/tesseract'
PKG = Path.home() / 'ftkb_djvu/pkg'
ENV = os.environ.copy()
ENV['LD_LIBRARY_PATH'] = str(PKG / 'usr/lib/x86_64-linux-gnu')
ENV['TESSDATA_PREFIX'] = str(PKG / 'usr/share/tesseract-ocr/4.00/tessdata')
ENV['OMP_THREAD_LIMIT'] = '1'


def recognize(row):
    started = time.monotonic()
    path = row['aliases'][0]['wsl']
    page = row['physical_page']
    try:
        render = subprocess.run(['pdftoppm', '-f', str(page), '-l', str(page),
                                 '-scale-to', '1800', '-gray', '-png', path],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        if render.returncode or not render.stdout:
            raise RuntimeError('render: ' + render.stderr[-250:].decode('utf8', 'replace'))
        lang = 'chi_sim+eng' if '/中文/' in path or any('\u4e00' <= c <= '\u9fff' for c in Path(path).name) else 'eng'
        result = subprocess.run([str(TESS), 'stdin', 'stdout', '-l', lang],
                                input=render.stdout, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=ENV, timeout=180)
        if result.returncode:
            raise RuntimeError('tesseract: ' + result.stderr[-250:].decode('utf8', 'replace'))
        return row, result.stdout.decode('utf8', 'replace').strip(), None, time.monotonic()-started
    except Exception as exc:
        return row, None, repr(exc), time.monotonic()-started


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--workers', type=int, default=6)
    args = ap.parse_args()
    if args.workers > 12:
        raise SystemExit('max 12 workers')
    ROOT.mkdir(exist_ok=True)
    db = sqlite3.connect(ROOT / 'ocr_round2.sqlite', timeout=90)
    db.execute('pragma journal_mode=WAL')
    db.execute('create table if not exists documents(sha256 text primary key, aliases_json text not null)')
    db.execute('create table if not exists pages(sha256 text not null, physical_page integer not null, chars integer not null, has_text integer not null, origin text not null, text text, primary key(sha256,physical_page), foreign key(sha256) references documents(sha256))')
    db.execute('create table if not exists errors(sha256 text, physical_page integer, error text, seconds real, primary key(sha256,physical_page))')
    finished = set(db.execute('select sha256,physical_page from pages')) | set(db.execute('select sha256,physical_page from errors'))
    rows = []
    with open(ROOT / 'ocr_round2.input.jsonl') as stream:
        for line in stream:
            r = json.loads(line)
            if (r['sha256'],r['physical_page']) not in finished:
                rows.append(r)
    rows.sort(key=lambda r: (r['priority'], r['aliases'][0]['wsl'], r['physical_page']))
    if args.limit:
        rows = rows[:args.limit]
    print('START', len(rows), 'already',len(finished),'workers',args.workers, flush=True)
    pending = {}
    pos = count = errors = empty = 0
    last = time.monotonic()
    start = last
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        while pos < len(rows) or pending:
            while pos < len(rows) and len(pending) < args.workers*2:
                future = pool.submit(recognize,rows[pos])
                pending[future] = rows[pos]
                pos += 1
            done, _ = cf.wait(pending, timeout=5, return_when=cf.FIRST_COMPLETED)
            for future in done:
                pending.pop(future)
                row,text,error,seconds = future.result()
                sha,page = row['sha256'],row['physical_page']
                if error:
                    db.execute('insert or replace into errors values(?,?,?,?)',(sha,page,error,seconds))
                    errors += 1
                else:
                    db.execute('insert or ignore into documents values(?,?)',(sha,json.dumps(row['aliases'],ensure_ascii=False)))
                    db.execute('insert or replace into pages values(?,?,?,?,?,?)',
                               (sha,page,len(text),int(bool(text)),'OCR 文本',text if text else None))
                    empty += not bool(text)
                count += 1
                if count % 10 == 0:
                    db.commit()
            now = time.monotonic()
            if now-last >= 60:
                db.commit()
                print('HEARTBEAT',count,'/',len(rows),'errors',errors,'empty',empty,
                      'wall_s',round(now-start,1),'db_bytes',(ROOT/'ocr_round2.sqlite').stat().st_size,
                      flush=True)
                last = now
    db.commit()
    print('DONE',count,'errors',errors,'empty',empty,'wall_s',round(time.monotonic()-start,1),flush=True)
    db.close()

if __name__ == '__main__':
    main()
