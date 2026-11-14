#!/usr/bin/env python3
"""CRC P1 132-run continuation; fail closed after three same-arm failures."""
import concurrent.futures, json, os, sys, traceback
from pathlib import Path
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
import crc_a170_2 as m

COHORTS=[('power','G1',range(1301,1337)),('power','G2',range(1301,1337)),
         ('power','G2Lc',range(1301,1337)),('wood','G1',range(1301,1313)),
         ('wood','G2Lc',range(1301,1313))]

def status(profile,group,seed):
    path=m.R/f'P1_{profile}_s{seed}_{group}.json'
    if not path.exists(): return None
    x=json.loads(path.read_text())
    if x.get('returncode')!=0: return 'failed'
    return 'success' if 'metrics' in x and 'yaw_rate_max_deg_s' in x else 'incomplete'

def do(profile,group,seed):
    p=json.loads((m.S/f'P1_{profile}_s{seed}'/'provenance.json').read_text())
    if group=='G1': hit=p['rotor_3s_first25_abs_s']
    elif group=='G2': hit=p['g2_trigger_abs_s']
    else:
        assert status(profile,'G1',seed)=='success',f'No baseline yaw for {profile}/{seed}'
        hit=m.g2lc_hit(seed,profile)
    return m.run_one(m.row(seed,profile,group,hit))

def run():
    import hashlib
    source=Path(os.environ['A170_SMOKE_GATE'])
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest==os.environ['A170_SMOKE_GATE_SHA256'], 'smoke gate hash mismatch'
    gate=json.loads(source.read_text())
    assert gate['status']=='passed' and set(gate['groups'])=={'G1','G2','G2Lc'}
    assert all(x['returncode']==0 and x['yaw_rate_max_deg_s']<=.31 for x in gate['groups'].values())
    if not m.P.exists():m.init()
    target=m.P/'smoke_gate.json'
    if not target.exists():target.write_bytes(source.read_bytes())
    assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
    n=int(os.environ.get('A170_WORKERS','8'))
    assert 1<=n<=int(os.environ.get('NSLOTS','8'))
    for profile,group,seeds in COHORTS:
        streak=0
        seeds=list(seeds)
        for offset in range(0,len(seeds),n):
            chunk=seeds[offset:offset+n]
            pending=[]
            for seed in chunk:
                existing=status(profile,group,seed)
                if existing=='success': print('REUSE',profile,group,seed,flush=True)
                elif existing is not None: raise RuntimeError(f'Preserve prior {existing}: {profile}/{group}/{seed}')
                else: pending.append(seed)
            # Spectral synthesis mutates the legacy module's coherence reference;
            # prepare fields serially before OpenFAST workers start.
            for seed in pending:m.make_seed(seed,profile)
            with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
                future={seed:pool.submit(do,profile,group,seed) for seed in pending}
                for seed in pending:
                    try:
                        result=future[seed].result()
                        assert result['returncode']==0
                        streak=0
                        print('OK',profile,group,seed,result['wall_s'],flush=True)
                    except Exception as exc:
                        streak+=1
                        print('FAIL',profile,group,seed,type(exc).__name__,str(exc),'streak',streak,flush=True)
                        if streak>=3:raise RuntimeError(f'3 consecutive failures: {profile}/{group}')
            m.checkpoint()
            (m.P/'batch_progress.json').write_text(json.dumps({'profile':profile,'group':group,'last_seed':chunk[-1],
               'counts':{f'{p}/{g}':sum(status(p,g,s)=='success' for s in ss) for p,g,ss in COHORTS}},indent=2))
    counts={f'{p}/{g}':sum(status(p,g,s)=='success' for s in seeds) for p,g,seeds in COHORTS}
    assert counts=={'power/G1':36,'power/G2':36,'power/G2Lc':36,'wood/G1':12,'wood/G2Lc':12},counts
    (m.P/'batch.done').write_text(json.dumps(counts,indent=2))
    print('BATCH_DONE',json.dumps(counts),flush=True)

if __name__=='__main__':
    try:run()
    except BaseException:
        traceback.print_exc()
        (m.P/'batch.failed').write_text(traceback.format_exc())
        sys.exit(1)
