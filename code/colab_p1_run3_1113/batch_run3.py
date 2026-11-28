#!/usr/bin/env python3
"""P1 paired full-duration runs, two workers at most; fail closed and checkpoint."""
import argparse, json, os, time, traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
os.environ.update(P1_SHA256='e55cf7ea02fa5fda56bf276883fb874ac2ac4145c9a4d5cf1f70d25d06f877fb', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
import colab_a170_2 as m
C=Path('/content'); R=Path('/content/a170_2/results')
COHORTS=[('power','G1',list(range(1301,1337))),('power','G2',list(range(1301,1337))),('power','G2Lc',list(range(1301,1337))),('wood','G1',list(range(1301,1313))),('wood','G2Lc',list(range(1301,1313)))]

def status(profile,group,seed):
    p=R/f'P1_{profile}_s{seed}_{group}.json'
    if not p.exists(): return None
    x=json.loads(p.read_text())
    if x['returncode']!=0: return 'failed'
    if 'metrics' not in x or 'yaw_rate_max_deg_s' not in x: return 'incomplete'
    return 'success'

def run():
    ap=argparse.ArgumentParser(); ap.add_argument('--timeout',type=int,required=True); ap.add_argument('--grace-seconds',type=int,default=9000); args=ap.parse_args()
    assert os.cpu_count()==2, os.cpu_count()
    os.environ['OPENFAST_TIMEOUT_S']=str(args.timeout)
    began=time.monotonic()
    m.old.P=m.P
    assert m.P.exists() and R.exists(), 'Restore prior checkpoint and initialized bundle before batch'
    for profile,group,seeds in COHORTS:
        streak=0
        for offset in range(0,len(seeds),2):
            pair=seeds[offset:offset+2]
            if time.monotonic()-began > args.grace_seconds:
                m.checkpoint()
                (C/'a170_2_batch.partial').write_text(json.dumps({'stage':[profile,group],'next_seed':pair[0],'elapsed_s':time.monotonic()-began}))
                print('GRACEFUL_PARTIAL',profile,group,pair[0],flush=True)
                return
            rows=[]
            for seed in pair:
                state=status(profile,group,seed)
                if state=='success':
                    print('REUSE',profile,group,seed,flush=True); streak=0; continue
                if state is not None: raise RuntimeError(f'Prior result {profile}/{group}/{seed} is {state}; do not overwrite')
                prov=m.make_seed(seed,profile)
                if group=='G1': hit=prov['rotor_3s_first25_abs_s']
                elif group=='G2': hit=prov['g2_trigger_abs_s']
                else:
                    assert status(profile,'G1',seed)=='success'
                    hit=m.g2lc_hit(seed,profile)
                rows.append(m.row(seed,profile,group,hit))
            if rows:
                with ThreadPoolExecutor(max_workers=min(2,len(rows))) as pool:
                    futures=[pool.submit(m.run_one,r) for r in rows]
                    for r,f in zip(rows,futures):
                        try:
                            x=f.result(); assert x['returncode']==0
                            streak=0; print('OK',profile,group,r['seed'],x['wall_s'],flush=True)
                        except Exception as e:
                            streak+=1; print('FAIL',profile,group,r['seed'],str(e),'streak',streak,flush=True)
                            if streak>=3: raise RuntimeError(f'Three consecutive failures in {profile} {group}')
            m.checkpoint()
    counts={f'{p}/{g}':sum(status(p,g,s)=='success' for s in seeds) for p,g,seeds in COHORTS}
    assert counts=={'power/G1':36,'power/G2':36,'power/G2Lc':36,'wood/G1':12,'wood/G2Lc':12},counts
    (C/'a170_2_batch.summary.json').write_text(json.dumps({'counts':counts,'elapsed_s':time.monotonic()-began},indent=2))
    (C/'a170_2_batch.done').write_text('success\n')
    print('BATCH_DONE',counts,flush=True)

if __name__=='__main__':
    try: run()
    except BaseException:
        (C/'a170_2_batch.failed').write_text(traceback.format_exc())
        traceback.print_exc()
        raise
