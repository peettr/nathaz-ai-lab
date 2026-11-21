#!/usr/bin/env python3
"""Bounded phase-by-phase evidence return from node scratch."""
import argparse,gzip,json,pathlib,shutil,time
p=argparse.ArgumentParser();p.add_argument('case');p.add_argument('out');p.add_argument('--once',action='store_true');a=p.parse_args()
c=pathlib.Path(a.case);out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
cap=250_000_000
files=('g1_progress.jsonl','g1_gate.json','g1_adjoint_gate.json','c2a_true_residual.json','g1_cp_trace.csv','meshconv_directions.json','meshconv_gradient_stats.json','meshconv_gradient.npy','c2a_direction_endpoints.jsonl','c2a_direction_rows.jsonl','system/fvSchemes')
def collect(seq,phase):
    receipt={'seq':seq,'phase':phase,'files':{}}
    for rel in files + (('g1_rank0.log',) if phase in ('final','ADJOINT_END','GRADIENT_SAVED') else ()):
        src=c/rel
        if not src.is_file(): continue
        name=out/f'{seq:04d}_{rel.replace("/","_")}.gz'
        if name.exists():continue
        # Reject before writing; compression might only reduce size, but reserve raw bytes.
        size=sum(f.stat().st_size for f in out.rglob('*') if f.is_file())
        if size+src.stat().st_size+1_000_000>cap:receipt['files'][rel]='CAP_SKIP';continue
        with name.open('xb') as f, gzip.GzipFile(fileobj=f,mode='wb',compresslevel=1) as z,src.open('rb') as inp:shutil.copyfileobj(inp,z)
        receipt['files'][rel]=name.stat().st_size
    print(json.dumps(receipt),flush=True)
seen=0
while True:
    progress=c/'g1_progress.jsonl'
    if progress.is_file():
        for line in progress.read_text(errors='replace').splitlines()[seen:]:
            seen+=1
            try:phase=json.loads(line)['phase']
            except (ValueError,KeyError):phase='unknown'
            collect(seen,phase)
    if a.once:collect(seen+1,'final');break
    time.sleep(10)
