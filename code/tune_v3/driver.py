"""L26.22-02d: three prespecified G tuning groups, no scoring objects.
Old groups are immutable; outputs are exclusive to tune_v3. Single CPU slot.
"""
import json, sys, time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path[:0]=[str(ROOT),str(ROOT/'tune_v1')]
import method_g as base
from optimized import activate
activate()
FROZEN=json.loads((base.SRC/'q1/tuning_selected_11f.json').read_text())['f']
ENTRIES=base.members('tuning')
CONFIGS=[{'W':30.,'lr':.01,'steps':10},
         {'W':30.,'lr':.005,'steps':10},
         {'W':30.,'lr':.01,'steps':20}]
START=time.perf_counter()

def trial(entry,ev,hyper,seed_no):
    seed=131+entry['index']*7+int(ev[0][-1])+(seed_no-1)*100000
    t=time.perf_counter()
    seq=base.run_sequence_g(base.Plant(base.Params(**entry['params'])),ev,hyper,seed=seed)
    official,chosen=base.official_g(entry,ev,seq)
    if official is None or not official['valid']:raise RuntimeError('invalid official tune score')
    delta=np.maximum(0,np.asarray(official['errors'])-np.asarray(FROZEN[f"{entry['index']}/{ev[0]}"]))
    return {'object':entry['index'],'event':ev[0],'seed':seed_no,
            'S':base.normalized(delta),'errors':official['errors'],
            'chosen_iteration':chosen,'valid_rounds':seq['valid_rounds'],
            'wall_s':time.perf_counter()-t}

def main():
    assert len(ENTRIES)==8 and len(base.TUNING)==2
    for idx,hyper in enumerate(CONFIGS,8):
        t=time.perf_counter();rows=[]
        with (HERE/f'group_{idx:02d}.jsonl').open('x') as f:
            for entry in ENTRIES:
                for ev in base.TUNING:
                    for seed_no in (1,2,3):
                        if (time.perf_counter()-START)/3600>4.8:
                            raise RuntimeError('tune_v3 hard budget stop; preserve partial, no scoring')
                        row=trial(entry,ev,hyper,seed_no)
                        f.write(json.dumps(row,allow_nan=False)+'\n');f.flush();rows.append(row)
                        print('TUNE_V3',idx,len(rows),'/48',flush=True)
        objects={str(e['index']):float(np.median([r['S'] for r in rows if r['object']==e['index']])) for e in ENTRIES}
        summary={'group':idx,'hyper':hyper,'object_median_S':objects,
                 'median_object_S':float(np.median(list(objects.values()))),
                 'wall_s':time.perf_counter()-t,'max_sequence_wall_s':max(r['wall_s'] for r in rows),
                 'count':len(rows)}
        with (HERE/f'group_{idx:02d}_summary.json').open('x') as f:json.dump(summary,f,indent=2)
        print('GROUP_DONE',json.dumps(summary),flush=True)
    with (HERE/'tuning_v3_elapsed.json').open('x') as f:
        json.dump({'elapsed_core_h':(time.perf_counter()-START)/3600,'groups':3},f,indent=2)
if __name__=='__main__':main()
