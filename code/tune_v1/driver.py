"""CRC single-process tune driver; exclusive results and hard 7 core-hour gate."""
import hashlib,json,sys,time,traceback
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import method_g as base
from optimized import activate

LIMIT=7*3600
START=time.perf_counter()
FROZEN=json.loads((base.SRC/'q1/tuning_selected_11f.json').read_text())['f']
ENTRIES=base.members('tuning')
assert len(ENTRIES)==8 and len(base.TUNING)==2

def elapsed():return time.perf_counter()-START

def save(name,record):
    with (HERE/name).open('x') as f:json.dump(record,f,ensure_ascii=False,indent=2,allow_nan=False)

def seed_for(entry,ev,seed_no):
    return 131+entry['index']*7+int(ev[0][-1])+(seed_no-1)*100000

def score(entry,ev,seq):
    result,chosen=base.official_g(entry,ev,seq)
    if result is None or not result['valid']:raise RuntimeError('invalid official score')
    delta=np.maximum(0,np.asarray(result['errors'])-np.asarray(FROZEN[f"{entry['index']}/{ev[0]}"]))
    return base.normalized(delta),result,chosen

def trial(entry,ev,hyper,seed_no):
    plant=base.Plant(base.Params(**entry['params']))
    s=seed_for(entry,ev,seed_no)
    t=time.perf_counter();seq=base.run_sequence_g(plant,ev,hyper,seed=s)
    value,official,chosen=score(entry,ev,seq)
    return {'object':entry['index'],'event':ev[0],'seed':seed_no,'S':value,
            'errors':official['errors'],'chosen_iteration':chosen,
            'valid_rounds':seq['valid_rounds'],'wall_s':time.perf_counter()-t}

def compare_pilot():
    entry=ENTRIES[0];ev=base.TUNING[0];hyper={'W':10.,'lr':.01,'steps':2}
    s=seed_for(entry,ev,1)
    t=time.perf_counter();old=base.run_sequence_g(base.Plant(base.Params(**entry['params'])),ev,hyper,seed=s)
    sold,_,_=score(entry,ev,old);old_t=time.perf_counter()-t
    activate()
    t=time.perf_counter();new=base.run_sequence_g(base.Plant(base.Params(**entry['params'])),ev,hyper,seed=s)
    snew,_,_=score(entry,ev,new);new_t=time.perf_counter()-t
    diffs=[abs(a['normalized_error']-b['normalized_error']) for a,b in zip(old['iterations'],new['iterations'])]
    cmds=[float(np.max(np.abs(np.asarray(a['command'])-np.asarray(b['command'])))) for a,b in zip(old['iterations'],new['iterations'])]
    report={'baseline':'1747066 did not save PILOT commands/S; same frozen code+seed reconstruction here, not byte comparison with that absent output',
            'seed':s,'hyper':hyper,'old_wall_s':old_t,'new_wall_s_including_first_jit_compile':new_t,
            'old_S':sold,'new_S':snew,'abs_S_diff':abs(sold-snew),
            'max_iteration_normalized_error_diff':max(diffs),'max_command_diff':max(cmds),
            'valid_rounds_old':old['valid_rounds'],'valid_rounds_new':new['valid_rounds']}
    save('pilot_compare.json',report)
    print('PILOT_COMPARE',json.dumps(report),flush=True)
    if report['abs_S_diff']>1e-9:raise RuntimeError('JIT reuse consistency gate failed')
    t=time.perf_counter();warm=trial(entry,ev,hyper,2)
    report2={'warm_sequence_wall_s_including_official':warm['wall_s'], 'S':warm['S'], 'seed':seed_for(entry,ev,2),
             'scoring_sequences':24*12*3,'scoring_core_hours_est_20pct':1.2*warm['wall_s']*864/3600,
             'tune_four_groups_core_hours_est_20pct':1.2*warm['wall_s']*4*48/3600}
    save('warm_budget.json',report2)
    print('WARM_BUDGET',json.dumps(report2),flush=True)
    # Include compilation of other W plus ample reserve; reject before consuming full grid.
    if elapsed()+1.2*warm['wall_s']*4*48+1800>LIMIT:
        raise RuntimeError('four groups forecast exceeds 7 core-hours')
    return report2

def run_group(idx,hyper):
    rows=[];t=time.perf_counter()
    file=HERE/f'group_{idx:02d}.jsonl'
    with file.open('x') as f:
        for entry in ENTRIES:
            for ev in base.TUNING:
                for seed_no in (1,2,3):
                    if elapsed()>LIMIT-420:raise RuntimeError('hard budget stop; incomplete group, no freeze')
                    row=trial(entry,ev,hyper,seed_no)
                    f.write(json.dumps(row,allow_nan=False)+'\n');f.flush();rows.append(row)
                    print('CASE',idx,len(rows),'/48',round(elapsed(),2),flush=True)
    objects={str(e['index']):float(np.median([r['S'] for r in rows if r['object']==e['index']])) for e in ENTRIES}
    summary={'group':idx,'hyper':hyper,'object_median_S':objects,
             'median_object_S':float(np.median(list(objects.values()))), 'wall_s':time.perf_counter()-t,'count':len(rows)}
    save(f'group_{idx:02d}_summary.json',summary)
    return summary

def main():
    budget=compare_pilot()
    summaries=[]
    for w in (10.,30.,60.):
        summaries.append(run_group(len(summaries),{'W':w,'lr':.01,'steps':2}))
    best=min(summaries,key=lambda x:(x['median_object_S'],x['group']))
    summaries.append(run_group(3,{'W':best['hyper']['W'],'lr':.04,'steps':2}))
    winner=min(summaries,key=lambda x:(x['median_object_S'],x['group']))
    conservative=max(s['wall_s']/s['count'] for s in summaries)
    scoring={'formula':'1.2 * max(measured group wall / 48 sequences) * 24 objects * 12 events * 3 seeds / 3600',
             'max_measured_wall_per_sequence_s':conservative,
             'estimated_scoring_core_hours_20pct':1.2*conservative*864/3600}
    save('tuning_summary.json',{'groups':summaries,'chosen':winner,'scoring_set_run':False,
                                'elapsed_core_hours':elapsed()/3600,'pilot':budget,'scoring_estimate':scoring})
    save('../frozen_config.json',{'method':'G','hyper':winner['hyper'],'group':winner['group'],
          'selection':'minimum median of 8 object medians, each object median over 2 events x 3 seeds',
          'source':'tune_v1/tuning_summary.json','scoring_set_run':False})
    digest=hashlib.sha256((HERE.parent/'frozen_config.json').read_bytes()).hexdigest()
    print('FROZEN',winner['group'],digest,'ELAPSED_H',elapsed()/3600,flush=True)
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:traceback.print_exc();raise
