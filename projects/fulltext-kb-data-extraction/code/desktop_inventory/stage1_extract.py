#!/usr/bin/env python3
"""Read-only desktop PDF text extraction; incremental, bounded local writes."""
import argparse, collections, hashlib, json, os, random, re, shlex, shutil, subprocess, sys, time, threading
from pathlib import Path
R=Path(__file__).resolve().parent
OUT=Path('./ftkb_desktop')
SOCKET='./.ssh/sockets/[邮箱]'
SSH=['ssh','-o',f'ControlPath={SOCKET}','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false','[邮箱]']
LIMIT=4*1024**3; MIN_FREE=40*1024**3

def source():
    hashes={x['path']:x['sha256'] for s in (R/'remote_hashes.jsonl').open() if (x:=json.loads(s)).get('sha256')}
    old={x['sha256'] for s in (R/'local_hashes.jsonl').open() if (x:=json.loads(s)).get('sha256')}
    rows=[]
    for s in (R/'remote_pdf_inspection.jsonl').open():
        x=json.loads(s); h=hashes.get(x['path'])
        if x.get('pages') and (not h or h not in old):
            x['sha256']=h; rows.append(x)
    assert len(rows)==12497 and sum(x['pages'] for x in rows)==421023,(len(rows),sum(x['pages'] for x in rows))
    return rows

def pathwin(p): return 'I:\\'+p[len('./'):].replace('/','\\')

def category(x):
    return ('Book' if x['path'].startswith('./Book/') else 'Literature',
            'CJKname' if re.search('[\u3400-\u9fff]',x['path'].split('/')[-1]) else 'other')

def pilot_selection(rows):
    rng=random.Random(20261014); groups=collections.defaultdict(list)
    for x in rows:groups[category(x)].append(x)
    # Explicit strata: 75 Book/CJK, 75 Book/other, 75 Literature/CJK, 75 Literature/other.
    selected=[]
    for k in sorted(groups): selected+=rng.sample(groups[k],75)
    rng.shuffle(selected)
    assert len(selected)==300
    return selected

def check_space(start_bytes,measure=True):
    avail=shutil.disk_usage('./').free
    if avail<MIN_FREE: raise RuntimeError(f'C盘剩余低于40GiB: {avail/2**30:.2f} GiB')
    total=int(subprocess.check_output(['du','-sb',str(OUT)]).split()[0]) if measure else -1
    if measure and total>LIMIT: raise RuntimeError(f'阶段新增超过4GiB: {total}')
    return avail,total

def extract(x):
    # One pdftotext invocation per document preserves physical page boundaries as form-feed.
    quoted=shlex.quote(x['path'])
    cmd='nice -n 19 ionice -c3 sh -c '+shlex.quote('sha256sum -- '+quoted+' && pdftotext -layout -enc UTF-8 '+quoted+' -')
    t=time.monotonic()
    p=subprocess.run(SSH+[cmd],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=900)
    elapsed=time.monotonic()-t
    if p.returncode: raise RuntimeError(f'exit={p.returncode} stderr={p.stderr[:250]!r}')
    header,body=p.stdout.split(b'\n',1)
    h=header[:64].decode('ascii')
    if not re.fullmatch('[0-9a-f]{64}',h) or (x['sha256'] and h!=x['sha256']): raise RuntimeError('sha256_mismatch')
    parts=body.decode('utf-8',errors='replace').split('\f')
    if len(parts)>x['pages'] and not parts[-1].strip():parts.pop()
    if len(parts)!=x['pages']: raise RuntimeError(f'page_boundary_mismatch: {len(parts)} != {x["pages"]}')
    return parts,elapsed,h

def run(rows,mode):
    OUT.mkdir(exist_ok=True)
    donefile=OUT/'stage1_done.jsonl'; man=OUT/'page_manifest.jsonl'; fail=OUT/'stage1_failures.jsonl'
    done={json.loads(s)['path'] for s in donefile.open()} if donefile.exists() else set()
    starts=time.monotonic(); checked=0; total_chars=0; textpages=0; zeropages=0; sample_seconds=0
    stop_heartbeat=threading.Event()
    def heartbeat():
        while not stop_heartbeat.wait(60):
            print(f'heartbeat mode={mode} elapsed_s={time.monotonic()-starts:.0f} completed_this_run={checked} total_done={len(done)}',flush=True)
    threading.Thread(target=heartbeat,daemon=True).start()
    with donefile.open('a') as d,man.open('a') as m,fail.open('a') as f:
        for x in rows:
            h=x['sha256']
            if x['path'] in done:continue
            try:
                parts,sec,h=extract(x)
                # SHA prefix collision guard; don't overwrite another content family.
                sub=OUT/'pages'/h[:8]
                if sub.exists() and (sub/'sha256').exists() and (sub/'sha256').read_text()!=h: raise RuntimeError('sha8_collision')
                sub.mkdir(parents=True,exist_ok=True)
                (sub/'sha256').write_text(h)
                paths=[{'wsl':p,'windows':pathwin(p)} for p in x['aliases']]
                page_rows=[]
                for i,part in enumerate(parts,1):
                    txt=part.strip()
                    # Control chars / blank page alone do not count as searchable text.
                    present=bool(re.search(r'[\w\u3400-\u9fff]',txt))
                    if present:
                        dest=sub/f'p{i:04d}.txt'
                        if dest.exists():
                            if dest.read_text()!=txt: raise RuntimeError(f'conflicting_existing_page_{i}')
                        else: dest.write_text(txt,encoding='utf-8')
                        total_chars+=len(txt);textpages+=1
                    else:zeropages+=1
                    page_rows.append({'sha256':h,'aliases':paths,'page':i,'physical_page':i,'chars':len(txt) if present else 0,'has_text':present,'text_path':str(sub/f'p{i:04d}.txt') if present else None})
                for row in page_rows:m.write(json.dumps(row,ensure_ascii=False)+'\n')
                m.flush();d.write(json.dumps({'sha256':h,'path':x['path'],'pages':x['pages'],'text_pages':sum(r['has_text'] for r in page_rows),'seconds':round(sec,3)},ensure_ascii=False)+'\n');d.flush()
                done.add(x['path']);sample_seconds+=sec;checked+=1
            except Exception as e:
                f.write(json.dumps({'sha256':h,'path':x['path'],'error':str(e)},ensure_ascii=False)+'\n');f.flush()
            if checked%10==0 and checked:
                avail,total=check_space(0,measure=(checked%100==0))
                print(f'{mode} completed_this_run={checked} total_done={len(done)} text_pages={textpages} empty_pages={zeropages} seconds={time.monotonic()-starts:.1f} stored_MiB={total/2**20:.1f} C_free_GiB={avail/2**30:.2f}',flush=True)
    stop_heartbeat.set()
    avail,total=check_space(0)
    print(json.dumps({'mode':mode,'completed_this_run':checked,'total_done':len(done),'text_pages_this_run':textpages,'empty_pages_this_run':zeropages,'chars_this_run':total_chars,'remote_seconds_this_run':sample_seconds,'wall_seconds':time.monotonic()-starts,'stored_bytes':total,'C_free_bytes':avail}),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['pilot','all']);args=ap.parse_args()
    rows=source()
    if args.mode=='pilot':
        sel=pilot_selection(rows)
        (OUT/'pilot_selection.jsonl').parent.mkdir(exist_ok=True)
        (OUT/'pilot_selection.jsonl').write_text(''.join(json.dumps({'sha256':x['sha256'],'path':x['path'],'pages':x['pages'],'stratum':category(x)},ensure_ascii=False)+'\n' for x in sel))
        rows=sel
    check_space(0)
    run(rows,args.mode)
