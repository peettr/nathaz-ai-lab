"""Resume only missing A170④ G2Lc cases from verified phase1 archive on a fresh CPU VM."""
import json, os, sys, time, tarfile, threading, traceback, concurrent.futures, hashlib
from pathlib import Path
sys.path.insert(0, '/content')
import colab_a170_4 as m
P=m.P; R=P/'results'
os.environ.update(R2_YAW_RATE='0.004188790204786391',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
ARCHIVE=Path('/content/a1704_recovery_0635.tar.gz')
EXPECTED_SHA='f2204f9c0cb9e84bf57eee98b1645a73502430fae5adaf06610273754194b596'
lock=threading.Lock(); stop=threading.Event()
def log(*x): print(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()), *x,flush=True)
def checkpoint():
    with lock:
        tmp=Path('/content/a170_4_phase2_checkpoint.tmp.tar.gz')
        with tarfile.open(tmp,'w:gz') as tf:
            for f in sorted(R.glob('*.json')): tf.add(f,arcname=f.name)
            for f in sorted(R.glob('*_G1_yaw.npz')): tf.add(f,arcname=f.name)
        tmp.replace('/content/a170_4_phase2_checkpoint.tar.gz')
def periodic():
    while not stop.wait(120):
        try: checkpoint()
        except Exception: traceback.print_exc()
def restore():
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()==EXPECTED_SHA,'recovery archive hash mismatch'
    with tarfile.open(ARCHIVE) as tf:
        items=tf.getmembers()
        assert len(items)==99 and all(x.isfile() and not x.issym() and not x.islnk() for x in items)
        assert all(x.name.startswith('results/') and '..' not in Path(x.name).parts for x in items)
        tf.extractall(P,filter='data')
    old=json.loads(Path('/content/r2_reuse_I_near.json').read_text())
    diffs={};bad=[]
    for s in m.ORIGINAL_SEEDS:
        fresh=json.loads((R/f'I_near_s{s}_G1.json').read_text())
        prior=old[f'I_near_s{s}_G1.json']
        d={k:abs(fresh['metrics'][k]-v)/max(abs(v),1e-12) for k,v in prior['metrics'].items()}
        diffs[str(s)]=max(d.values())
        if max(d.values())>.005:bad.append(s)
    gate=dict(original_seed_count=12,per_seed_max_relative=diffs,failed_seeds=bad,passes=not bad,threshold=.005)
    (R/'old12_replay_gate.json').write_text(json.dumps(gate,indent=2));checkpoint();log('REPLAY_GATE',bad)
    assert not bad,'old G1 replay >0.5%, stop before G2Lc'
def run_one(seed):
    r=m.g2lc_row(seed)
    if r['trigger_abs_s'] is None:
        x=m.run_one(dict(r,trigger_abs_s=r['end_abs_s']+100),shutdown=False)
        x['trigger_abs_s']=None;x['not_triggered']=True
        (R/f'I_near_s{seed}_G2Lc.json').write_text(json.dumps(x,indent=2))
    else:x=m.run_one(r)
    return x
def main():
    log('SETUP');m.setup();restore()
    c=m.case_list(m.mods()[2])[0][0]
    # Rebuild source wind fields from the same code/seed; never replay completed G1/G2.
    for s in m.SEEDS: m.make_storm(c,'I_near',s)
    log('FIELDS_READY',len(m.SEEDS))
    seeds=[s for s in m.SEEDS if not (R/f'I_near_s{s}_G2Lc.json').exists()]
    assert len(seeds)==35,('expected 35 remaining G2Lc',len(seeds))
    checkpoint()
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for x in pool.map(run_one,seeds):
            log('G2LC',x['seed'],x['returncode'],x.get('yaw_rate_max_deg_s'))
            checkpoint()
            assert x['returncode']==0,('G2Lc failed',x['seed'],x.get('error_tail'))
    assert all((R/f'I_near_s{s}_G2Lc.json').exists() for s in m.SEEDS)
    (R/'continuation_complete.json').write_text(json.dumps(dict(old_g1=12,new_g1_g2=24,all_g2lc=36,all_solvers=96)))
    checkpoint();log('PHASE2_COMPLETE')
if __name__=='__main__':
    threading.Thread(target=periodic,daemon=True).start()
    try:main();Path('/content/a170_4_phase2.done').write_text('ok\n')
    except BaseException:traceback.print_exc();Path('/content/a170_4_phase2.failed').write_text(traceback.format_exc())
    finally:
        stop.set()
        try:checkpoint()
        except Exception:traceback.print_exc()
