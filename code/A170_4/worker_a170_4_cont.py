"""Authorized A170④ continuation on the EXISTING phase1 VM only.
Run after phase1.done; stop before G2Lc if any original-seed G1 differs >0.5%.
"""
import json, os, sys, time, tarfile, threading, traceback
from pathlib import Path
sys.path.insert(0, '/content')
import colab_a170_4 as m
P=m.P; R=P/'results'; OLD=m.ORIGINAL_SEEDS; NEW=m.NEW_SEEDS
os.environ.update(R2_YAW_RATE='0.004188790204786391', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
stop=threading.Event()
def log(*x): print(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()), *x, flush=True)
def checkpoint():
    tmp=Path('/content/a170_4_cont_checkpoint.tmp.tar.gz')
    with tarfile.open(tmp,'w:gz') as tf:
        for f in R.glob('*.json'): tf.add(f,arcname=f.name)
        for f in R.glob('*_G1_yaw.npz'): tf.add(f,arcname=f.name)
    tmp.replace('/content/a170_4_cont_checkpoint.tar.gz')
    # Existing hard-stop timer pulls this fixed remote path at its deadline.
    import shutil
    shutil.copy2('/content/a170_4_cont_checkpoint.tar.gz','/content/a170_4_checkpoint.tar.gz')
def periodic():
    while not stop.wait(120):
        try: checkpoint()
        except Exception: traceback.print_exc()
def row(seed,group,hit):
    root=P/'runs'/f'I_near_s{seed}';p=json.loads((root/'provenance.json').read_text())
    return dict(case='I_near',seed=seed,group=group,source=str(root),start_abs_s=p['start_abs_s'],end_abs_s=p['end_abs_s'],trigger_abs_s=hit)
def run_g2lc(seed):
    r=m.g2lc_row(seed)
    if r['trigger_abs_s'] is None:
        x=m.run_one(dict(r,trigger_abs_s=r['end_abs_s']+100),shutdown=False)
        x['trigger_abs_s']=None;x['not_triggered']=True
        (R/f'I_near_s{seed}_G2Lc.json').write_text(json.dumps(x,indent=2))
        return x
    return m.run_one(r)
def main():
    assert Path('/content/a170_4_phase1.done').exists() and not Path('/content/a170_4_phase1.failed').exists(), 'phase1 not successful'
    base=json.loads(Path('/content/r2_reuse_I_near.json').read_text());assert len(base)==36
    c=m.case_list(m.mods()[2])[0][0]
    for s in OLD[1:]:
        root=P/'runs'/f'I_near_s{s}'
        if not (root/'provenance.json').exists():m.make_storm(c,'I_near',s)
    log('OLD_FIELDS_READY')
    # This is the ONLY tranche before the mandatory all-12 replay parity gate.
    for s in OLD[1:]:
        p=json.loads((P/'runs'/f'I_near_s{s}'/'provenance.json').read_text())
        x=m.run_one(row(s,'G1',p['rotor_3s_first25_abs_s']))
        assert x['returncode']==0, ('G1 solver failed',s,x.get('error_tail'))
        checkpoint();log('G1_REPLAY',s)
    diffs={};bad=[]
    for s in OLD:
        old=base[f'I_near_s{s}_G1.json'];new=json.loads((R/f'I_near_s{s}_G1.json').read_text())
        d={k:abs(new['metrics'][k]-v)/max(abs(v),1e-12) for k,v in old['metrics'].items()}
        diffs[str(s)]=dict(fields=d,max_relative=max(d.values()),old_rate=old['yaw_rate_max_deg_s'],new_rate=new['yaw_rate_max_deg_s'])
        if max(d.values())>.005: bad.append(s)
    gate=dict(original_seed_count=12,per_seed=diffs,failed_seeds=bad,passes=not bad,threshold=.005)
    (R/'old12_replay_gate.json').write_text(json.dumps(gate,indent=2));checkpoint();log('REPLAY_GATE',bad)
    assert not bad, 'old G1 replay >0.5%; no more G2Lc'
    for s in NEW:
        if not (R/f'I_near_s{s}_G2Lc.json').exists():
            x=run_g2lc(s);assert x['returncode']==0,('new G2Lc failed',s)
            checkpoint();log('NEW_G2LC',s)
    for s in OLD[1:]:
        if not (R/f'I_near_s{s}_G2Lc.json').exists():
            x=run_g2lc(s);assert x['returncode']==0,('old G2Lc failed',s)
            checkpoint();log('OLD_G2LC',s)
    (R/'continuation_complete.json').write_text(json.dumps(dict(old_g1=12,new_g1_g2=24,all_g2lc=36,all_solvers=96)))
    checkpoint();log('CONT_COMPLETE')
if __name__=='__main__':
    threading.Thread(target=periodic,daemon=True).start()
    try:main();Path('/content/a170_4_cont.done').write_text('ok\n')
    except BaseException:traceback.print_exc();Path('/content/a170_4_cont.failed').write_text(traceback.format_exc())
    finally:
        stop.set()
        try:checkpoint()
        except Exception:traceback.print_exc()
