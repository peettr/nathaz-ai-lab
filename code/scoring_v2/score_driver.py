"""L26.22-02e scoring, with first-case smoke gate and 14 core-hour hard cap.
Uses original official scorer and immutable v2 freeze; no tuning writes.
"""
import json, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
HERE=ROOT/'scoring_v2'
sys.path[:0]=[str(ROOT),str(ROOT/'tune_v1'),str(ROOT/'from_L30.1f/q1')]
import method_g as base
from common import EVENTS
from optimized import activate
activate()
START=time.perf_counter()
CAP_S=14*3600
# Leave room for the last sequence and output flushing; scheduler also limits 14 h.
STOP_S=CAP_S-180

def row_for(entry,ev,seed_no,hyper):
    seed=131+entry['index']*7+int(ev[0][-1])+(seed_no-1)*100000
    seq=base.run_sequence_g(base.Plant(base.Params(**entry['params'])),ev,hyper,seed=seed)
    official,chosen=base.official_g(entry,ev,seq)
    last=seq['iterations'][-1]
    last_official=base.official(entry,ev,{'method':'G','best_command':last['command'],'best_warp':None})
    return {'object':entry['index'],'event':ev[0],'method':'G','seed':seed_no,
            'e':None if official is None else official['errors'],
            'last_e':None if last_official is None else last_official['errors'],
            'official_valid':bool(official is not None and official['valid']),
            'best_iteration':chosen,'valid_rounds':seq['valid_rounds'],
            'last_valid':last['valid']}

def validate(row):
    assert row['official_valid'] and row['e'] is not None and len(row['e'])==3
    assert row['last_e'] is not None and len(row['last_e'])==3
    assert row['best_iteration'] is not None and 1<=row['best_iteration']<=25

def main():
    frozen=json.loads((ROOT/'frozen_config_v2.json').read_text())
    assert frozen['group']==6 and frozen['hyper']=={'W':30.0,'lr':0.01,'steps':5}
    entries=json.loads((base.SRC/'v8b/scoring.json').read_text())
    assert len(entries)==24 and len(EVENTS)==12 and len({e['index'] for e in entries})==24
    assert not (HERE/'results_G.jsonl').exists() and not (HERE/'smoke.json').exists()
    hyper=frozen['hyper']
    smoke=row_for(entries[0],EVENTS[0],1,hyper)
    validate(smoke)
    with (HERE/'smoke.json').open('x') as f:json.dump(smoke,f,indent=2)
    print('SMOKE_PASS',json.dumps(smoke),flush=True)
    count=0;valid=0;seen=set()
    with (HERE/'results_G.jsonl').open('x') as f:
        for entry in entries:
            for ev in EVENTS:
                for seed_no in (1,2,3):
                    if time.perf_counter()-START>=STOP_S:
                        print('STOP scoring 14 core-hour cap; partial rows retained',flush=True)
                        return
                    row=smoke if (entry is entries[0] and ev is EVENTS[0] and seed_no==1) else row_for(entry,ev,seed_no,hyper)
                    key=(row['object'],row['event'],row['seed']);assert key not in seen
                    seen.add(key);count+=1;valid+=row['official_valid']
                    f.write(json.dumps(row,allow_nan=False)+'\n');f.flush()
                    print('SCORE',count,'/864',flush=True)
    assert count==864 and len(seen)==864
    with (HERE/'completion.json').open('x') as f:
        json.dump({'count':count,'valid':valid,'scoring_elapsed_core_h':(time.perf_counter()-START)/3600},f,indent=2)
if __name__=='__main__':main()
