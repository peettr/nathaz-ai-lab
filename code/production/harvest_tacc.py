#!/usr/bin/env python3
"""Immutable, bounded snapshots from node scratch to TACC scratch root."""
import argparse, gzip, json, os, pathlib, shutil, time
p=argparse.ArgumentParser(); p.add_argument('case'); p.add_argument('out'); p.add_argument('--once',action='store_true'); a=p.parse_args()
c=pathlib.Path(a.case); out=pathlib.Path(a.out); out.mkdir(parents=True,exist_ok=True)
cap=250_000_000; seen=0
files=['g1_progress.jsonl','g1_gate.json','g1_adjoint_gate.json','c2a_true_residual.json','c2a_direction_vectors.json','c2a_direction_endpoints.jsonl','c2a_direction_rows.jsonl','g1_cp_trace.csv','g1_gate_error.txt','system/fvSchemes']
def used(): return sum(f.stat().st_size for f in out.rglob('*') if f.is_file())
def collect(n,phase):
    receipt={'seq':n,'phase':phase,'files':{}}
    for rel in files+(['g1_rank0.log'] if phase not in ('COLD_ENDPOINT','DIRECTION_FD') else []):
        src=c/rel
        if not src.is_file(): continue
        raw=src.stat().st_size
        name=out/f'{n:04d}_{rel.replace("/","_")}.gz'
        if name.exists(): continue
        if used()+raw+1_000_000>cap: receipt['files'][rel]='CAP_SKIP'; continue
        with name.open('xb') as f, gzip.GzipFile(fileobj=f,mode='wb',compresslevel=1) as z, src.open('rb') as inp: shutil.copyfileobj(inp,z)
        receipt['files'][rel]=name.stat().st_size
    print(json.dumps(receipt),flush=True)
while True:
    src=c/'g1_progress.jsonl'
    if src.exists():
        lines=src.read_text(errors='replace').splitlines()
        for line in lines[seen:]:
            seen+=1
            try: phase=json.loads(line)['phase']
            except (ValueError,KeyError): phase='unknown'
            collect(seen,phase)
    if a.once: collect(seen+1,'final');break
    time.sleep(10)
