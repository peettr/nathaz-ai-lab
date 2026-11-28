"""Four additional prespecified tuning groups, then conditional single scoring set.
Runs in one CPU slot; never changes tune_v1 or source data. All outputs exclusive.
"""
import hashlib, json, sys, time, traceback
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tune_v1'))
import method_g as base
from optimized import activate
activate()
OLD=HERE/'tune_v1_summary.json'  # exact prior result snapshot, hash-checked on stage
FROZEN=json.loads((base.SRC/'q1/tuning_selected_11f.json').read_text())['f']
ENTRIES=base.members('tuning')
START=time.perf_counter()
PROJECT_PRIOR_H=0.057017+1.7469171004680943
PROJECT_CAP_H=30.
CONFIGS=[{'W':30.,'lr':.005,'steps':2},{'W':30.,'lr':.005,'steps':5},
         {'W':30.,'lr':.01,'steps':5},{'W':30.,'lr':.02,'steps':5}]

def save(path,obj):
    with path.open('x') as f: json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)

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

def tune():
    assert len(ENTRIES)==8 and len(base.TUNING)==2
    old=json.loads(OLD.read_text())['groups']
    assert len(old)==4 and [s['group'] for s in old]==list(range(4))
    new=[]
    for idx,hyper in enumerate(CONFIGS,4):
        t=time.perf_counter();rows=[]
        with (HERE/f'group_{idx:02d}.jsonl').open('x') as f:
            for entry in ENTRIES:
                for ev in base.TUNING:
                    for seed_no in (1,2,3):
                        if (time.perf_counter()-START)/3600>6.9:
                            raise RuntimeError('budget stop before completing tuning; preserve partial')
                        row=trial(entry,ev,hyper,seed_no)
                        f.write(json.dumps(row,allow_nan=False)+'\n');f.flush();rows.append(row)
                        print('TUNE',idx,len(rows),'/48',flush=True)
        objects={str(e['index']):float(np.median([r['S'] for r in rows if r['object']==e['index']])) for e in ENTRIES}
        summary={'group':idx,'hyper':hyper,'object_median_S':objects,
                 'median_object_S':float(np.median(list(objects.values()))),
                 'wall_s':time.perf_counter()-t,'count':len(rows)}
        save(HERE/f'group_{idx:02d}_summary.json',summary);new.append(summary)
    allgroups=old+new
    winner=min(allgroups,key=lambda s:(s['median_object_S'],s['group']))
    # The selected group's observed mean is a direct measurement, not a pilot shortcut.
    per_seq=winner['wall_s']/winner['count']
    scoring_est=1.2*per_seq*864/3600
    used=PROJECT_PRIOR_H+(time.perf_counter()-START)/3600
    gate=used+scoring_est<=PROJECT_CAP_H
    budget={'prior_core_h':PROJECT_PRIOR_H,'new_tuning_core_h':(time.perf_counter()-START)/3600,
            'measured_selected_group_sequence_wall_s':per_seq,
            'scoring_est_core_h_20pct':scoring_est,'projected_total_core_h':used+scoring_est,
            'cap_core_h':PROJECT_CAP_H,'scoring_gate_pass':gate,
            'formula':'prior + new tuning + 1.2 * selected-group wall_s / 48 * 864 / 3600'}
    save(HERE/'tuning_summary_8groups.json',{'groups':allgroups,'chosen':winner,'budget':budget})
    save(ROOT/'frozen_config_v2.json',{'method':'G','hyper':winner['hyper'],'group':winner['group'],
         'selection':'minimum median of 8 object medians, each median over 2 events x 3 seeds',
         'source':'tune_v1/results_1747115/tune_v1/tuning_summary.json + tune_v2/tuning_summary_8groups.json',
         'scoring_set_run_at_freeze':False})
    print('FROZEN_V2',winner['group'],hashlib.sha256((ROOT/'frozen_config_v2.json').read_bytes()).hexdigest(),flush=True)
    print('BUDGET',json.dumps(budget),flush=True)
    return winner,budget

def score_from_frozen():
    summary=json.loads((HERE/'tuning_summary_8groups.json').read_text())
    winner,budget=summary['chosen'],summary['budget']
    assert json.loads((ROOT/'frozen_config_v2.json').read_text())['group']==winner['group']
    assert budget['scoring_gate_pass']
    score(winner,budget)

def score(winner,budget):
    if not budget['scoring_gate_pass']:
        print('STOP scoring projected > 30 core-h',flush=True);return
    entries=json.loads((base.SRC/'v8b/scoring.json').read_text())  # frozen SHA-256 15b2c59f...
    assert len(entries)==24 and len(base.EVENTS)==12
    hyper=winner['hyper']
    out=ROOT/'scoring_v1'
    out.mkdir(exist_ok=True)
    assert not (out/'results_G.jsonl').exists(), 'score already started'
    seen=set()
    with (out/'results_G.jsonl').open('x') as f:
        for entry in entries:
            for ev in base.EVENTS:
                for seed_no in (1,2,3):
                    if PROJECT_PRIOR_H+budget['new_tuning_core_h']+(time.perf_counter()-START)/3600>=PROJECT_CAP_H-0.1:
                        raise RuntimeError('hard project 30 core-hour stop; scoring incomplete')
                    seed=131+entry['index']*7+int(ev[0][-1])+(seed_no-1)*100000
                    seq=base.run_sequence_g(base.Plant(base.Params(**entry['params'])),ev,hyper,seed=seed)
                    official,chosen=base.official_g(entry,ev,seq)
                    # Last-round diagnostic uses the same 120+1800 s official scorer.
                    last=seq['iterations'][-1]
                    last_official=base.official(entry,ev,{'method':'G','best_command':last['command'],'best_warp':None})
                    row={'object':entry['index'],'event':ev[0],'method':'G','seed':seed_no,
                         'e':None if official is None else official['errors'],
                         'last_e':None if last_official is None else last_official['errors'],
                         'last_e_source':'official 120 s settle + 1800 s scoring',
                         'official_valid':bool(official is not None and official['valid']),
                         'best_iteration':chosen,'valid_rounds':seq['valid_rounds'],
                         'last_valid':last['valid']}
                    key=(row['object'],row['event'],row['seed']);assert key not in seen
                    seen.add(key);f.write(json.dumps(row,allow_nan=False)+'\n');f.flush()
                    print('SCORE',len(seen),'/864',flush=True)
    assert len(seen)==864
    save(out/'completion.json',{'count':len(seen),'valid':sum(json.loads(line)['official_valid'] for line in (out/'results_G.jsonl').read_text().splitlines()),
                                'elapsed_core_h_total_est':PROJECT_PRIOR_H+budget['new_tuning_core_h']+(time.perf_counter()-START)/3600})

def main():
    if len(sys.argv)!=2 or sys.argv[1] not in ('tune','score'):
        raise SystemExit('usage: driver.py tune|score')
    if sys.argv[1]=='tune':tune()
    else:score_from_frozen()
if __name__=='__main__':
    try:main()
    except Exception:traceback.print_exc();raise
