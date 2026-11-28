"""L0h bounded rejection sampling of frozen L0b geometry. No matrix persistence.
Source: L0b parameter table; rejected sample is not used for training/evaluation.
"""
import argparse, concurrent.futures, json, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from l0b_generate import make_sample

SPLITS={'train': (110000,250), 'val': (210000,5), 'test': (310000,100)}
GEOMETRIES=('convex','holed','simple_polygon')

def attempt(item):
    split, kind, seed = item
    try:
        A, b, meta=make_sample(seed,kind)
        return {'split':split,'geometry':kind,'seed':seed,'n':int(A.shape[0]),
                'nnz':int(A.nnz),'status':'accepted'}
    except (ValueError, RuntimeError) as exc:
        return {'split':split,'geometry':kind,'seed':seed,'status':'rejected',
                'reason':str(exc)[:240]}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',required=True)
    p.add_argument('--workers',type=int,default=4); p.add_argument('--batch',type=int,default=24)
    p.add_argument('--max-attempt-factor',type=int,default=10)
    args=p.parse_args(); assert 1<=args.workers<=4 and args.batch>=args.workers
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists(): raise FileExistsError(out)
    started=time.monotonic(); groups={}; accepted=[]; rejected=[]
    # Per-split/class non-overlapping seed sequences: base + 3*index + class.
    # Initial 750/15/300 identities remain first attempts; rejected positions
    # are replaced by higher unused seeds within their split's reserved range.
    for split,(base,target) in SPLITS.items():
        for kind in range(3):
            good=[]; tried=0
            with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
                while len(good)<target:
                    if tried>=target*args.max_attempt_factor:
                        raise RuntimeError(f'rejection cap {split}/{kind} {len(good)}/{target}')
                    batch=min(args.batch,target*args.max_attempt_factor-tried)
                    tasks=((split,kind,base+3*i+kind) for i in range(tried,tried+batch))
                    for row in pool.map(attempt,tasks):
                        if row['status']=='accepted' and len(good)<target:
                            good.append({k:row[k] for k in ('split','geometry','seed','n','nnz')})
                        elif row['status']=='rejected': rejected.append(row)
                        # Successful excess candidates are unused (not rejected).
                    tried+=batch
                    print(f'PROGRESS {split} {GEOMETRIES[kind]} accepted={len(good)}/{target} attempted={tried}',flush=True)
            accepted.extend(good)
            groups[f'{split}/{GEOMETRIES[kind]}']={'accepted':len(good),'attempted':tried,
                 'rejected':sum(x['split']==split and x['geometry']==kind for x in rejected),
                 'unused_valid':tried-len(good)-sum(x['split']==split and x['geometry']==kind for x in rejected)}
            groups[f'{split}/{GEOMETRIES[kind]}']['rejection_rate']=groups[f'{split}/{GEOMETRIES[kind]}']['rejected']/tried
    assert len(accepted)==1065 and len({r['seed'] for r in accepted})==1065
    assert all(20000<=r['n']<=100000 and r['nnz']<=500000 for r in accepted)
    payload={'status':'complete','source':'L0b reconstructed P1 Poisson; L0h rejection sampling',
      'accepted':accepted,'counts':groups,'rejected_count':len(rejected),
      'wall_seconds':time.monotonic()-started,'workers':args.workers,
      'rejected_examples':rejected[:30]}
    with out.open('x') as f: json.dump(payload,f,indent=2,allow_nan=False)
    print('ACCEPTED_TABLE',str(out),'N',len(accepted),'GROUPS',json.dumps(groups),flush=True)

if __name__=='__main__': main()
