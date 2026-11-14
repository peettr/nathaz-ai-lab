#!/usr/bin/env python3
"""Post hoc Wood sensitivity expansion: only seeds 1313..1336, G1/G2Lc.
Never imports or overwrites the original 132-run root.
"""
import concurrent.futures as cf
import json, os, sys, traceback
from pathlib import Path
os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
import crc_a170_2 as m
SEEDS=list(range(1313,1337))
COHORTS=('G1','G2Lc')

def status(group,seed):
    p=m.R/f'P1_wood_s{seed}_{group}.json'
    if not p.exists(): return None
    x=json.loads(p.read_text())
    if x.get('returncode')!=0: return 'failed'
    return 'success' if isinstance(x.get('metrics'),dict) and 'yaw_rate_max_deg_s' in x else 'incomplete'

def run_one(group,seed):
    p=json.loads((m.S/f'P1_wood_s{seed}'/'provenance.json').read_text())
    hit=p['rotor_3s_first25_abs_s'] if group=='G1' else m.g2lc_hit(seed,'wood')
    if group=='G2Lc': assert status('G1',seed)=='success'
    return m.run_one(m.row(seed,'wood',group,hit))

def run():
    if not m.P.exists(): m.init()
    else:
        m.old.P=m.P
        assert m.checksum(os.environ['A170_P1'])==os.environ['P1_SHA256']
    workers=int(os.environ.get('A170_WORKERS','8'))
    assert 1<=workers<=int(os.environ.get('NSLOTS','8'))
    for group in COHORTS:
        streak=0
        for pos in range(0,len(SEEDS),workers):
            chunk=SEEDS[pos:pos+workers]
            pending=[]
            for seed in chunk:
                prev=status(group,seed)
                if prev=='success': print('REUSE',group,seed,flush=True)
                elif prev is not None: raise RuntimeError(f'Preserve prior {prev}: {group}/{seed}')
                else: pending.append(seed)
            # Synthesis changes shared legacy coherence state: prepare serially.
            for seed in pending: m.make_seed(seed,'wood')
            with cf.ThreadPoolExecutor(max_workers=workers) as pool:
                futures={s:pool.submit(run_one,group,s) for s in pending}
                for seed in pending:
                    try:
                        result=futures[seed].result()
                        assert result['returncode']==0
                        streak=0
                        print('OK',group,seed,result['wall_s'],flush=True)
                    except Exception as e:
                        streak+=1
                        print('FAIL',group,seed,type(e).__name__,str(e),'streak',streak,flush=True)
                        if streak>=3: raise RuntimeError(f'3 consecutive failures: wood/{group}')
            m.checkpoint()
            (m.P/'batch_progress.json').write_text(json.dumps({
                'group':group,'last_seed':chunk[-1],
                'counts':{g:sum(status(g,s)=='success' for s in SEEDS) for g in COHORTS}},indent=2))
    counts={g:sum(status(g,s)=='success' for s in SEEDS) for g in COHORTS}
    assert counts=={'G1':24,'G2Lc':24},counts
    (m.P/'batch.done').write_text(json.dumps(counts,indent=2))
    print('WOOD36_DONE',json.dumps(counts),flush=True)

if __name__=='__main__':
    try: run()
    except BaseException:
        traceback.print_exc()
        m.P.mkdir(parents=True,exist_ok=True)
        (m.P/'batch.failed').write_text(traceback.format_exc())
        sys.exit(1)
