"""Tuning set only; stage ② runs after stage ① reference gate.

No scoring-set method runs here. Commands from reference.py are never imported.
"""
import argparse,hashlib,json,os
from pathlib import Path
import numpy as np
from common import Params,Plant,TUNING,LO,HI,evaluate,errors,members,normalized
from methods import run_sequence
from gca_spectrum import warped_rows

METHODS=('A0','A1','A2','A3','A4')
HYPER={
 'A0':[{}],
 'A1':[{'probes':p,'ridge':r} for p in (2,4,8) for r in (.02,.2)],
 'A2':[{'K_FFM':kf,'K_TF':kt,'K_VAF':kv,'K_warp':kw,'F_c':fc}
       for kf,kt in ((.2,.005),(.6,.02))
       for kv,kw in ((.04,.08),(.12,.2)) for fc in (1.5,6.)],
 'A3':[{'probes':p,'ridge':r,'probe_design':d} for p in (2,4,8) for r in (.02,.2) for d in ('random','grouped')],
 'A4':[{'probes':p,'ridge':r,'probe_design':d} for p in (2,4,8) for r in (.02,.2) for d in ('random','grouped')]}
assert all(len(v)<=12 for v in HYPER.values())

def official(entry,event,sequence,smoke=False):
    x=sequence['best_command']
    if x is None:return None
    p=Params(**entry['params'])
    if sequence['method']=='A2' and sequence['best_warp'] is not None:
        x=np.asarray(x,float);warp=np.asarray(sequence['best_warp'])
        from dataclasses import replace
        from plant import score,metrics
        pp=replace(p,drift=0.)
        seeds=(1001,) if smoke else (1001,1002,1003)
        n=int(round((3. if smoke else 1800.)*p.fs));settle=int(round(120*p.fs))
        values=[];valid=[];ratios=[]
        for measurement_seed,command_seed in zip(seeds,(2001,2002,2003)):
            wave=warped_rows(x,p,200.,command_seed,warp)
            rows=wave[:,np.arange(n+settle)%wave.shape[1]]
            plant=Plant(pp)
            plant.run(float(x[0]),rows[:,:settle],x[25:27],120.,sample=False)
            r=plant.run(float(x[0]),rows[:,settle:],x[25:27],n/p.fs,seed=measurement_seed)
            values.append(metrics(r['series'],1/p.fs));valid.append(r['valid']);ratios.append(r['min_ratio'])
        obs={name:np.mean([v[name] for v in values],axis=0) for name in ('u','Iu','Lux')}
        e=errors(obs,event);valid=all(valid);min_ratio=min(ratios)
    else:
        e,r=evaluate(p,x,event,duration=3. if smoke else 1800.,
                     seeds=(1001,) if smoke else (1001,1002,1003),
                     command_seeds=(2001,) if smoke else (2001,2002,2003))
        valid=bool(r['valid']);min_ratio=r['min_ratio']
    return {'errors':e.tolist(),'valid':valid,'min_ratio':min_ratio}

def bounds(path):
    records=[json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]
    result={(r['object'],r['event']):r for r in records}
    if len(records)!=16 or len(result)!=16:raise RuntimeError('expected 16 distinct tuning reference records')
    return result

def reduce_trials(trials, lower):
    """Freeze f only AFTER every candidate has an official score; no reference commands."""
    keys={(e['index'],event[0]) for e in members('tuning') for event in TUNING}
    if set(lower)!=keys:raise RuntimeError('tuning reference keys mismatch')
    sources={key:[None]*3 for key in keys};f={key:[float('inf')]*3 for key in keys}
    def offer(key,values,origin):
        for i,value in enumerate(values):
            if value is not None and np.isfinite(value) and value<f[key][i]:
                f[key][i]=float(value);sources[key][i]=origin
    for key,row in lower.items():
        if not row.get('no_valid'):
            offer(key,[row['f_u'],row['f_I'],row['f_L']],'reference')
    for trial in trials:
        for case in trial['cases']:
            val=case['official'];key=(case['object'],case['event'])
            if key not in f:raise RuntimeError('unexpected tuning case')
            if val and val['valid']:
                offer(key,val['errors'],'method')
    excluded=[key for key in sorted(keys) if not all(np.isfinite(f[key]))]
    counts={origin:sum(src==origin for row in sources.values() for src in row) for origin in ('reference','method')}
    reduced=[]
    for trial in trials:
        rec={k:v for k,v in trial.items() if k!='cases'}
        cases=[]
        for case in trial['cases']:
            key=(case['object'],case['event']);val=case['official']
            score=(normalized(np.maximum(0.,np.asarray(val['errors'])-f[key]))
                   if key not in excluded and val and val['valid'] else None)
            cases.append({**case,'S':score})
        scores=[c['S'] for c in cases if c['S'] is not None]
        rec.update(cases=cases,median_S=float(np.median(scores)) if scores else None,
                   valid_cases=len(scores),eligible_cases=len(keys)-len(excluded))
        reduced.append(rec)
    return reduced,{'f':{f'{k[0]}/{k[1]}':v if k not in excluded else None for k,v in sorted(f.items())},
                    'sources':{f'{k[0]}/{k[1]}':v for k,v in sorted(sources.items())},
                    'source_component_counts':counts,'excluded_no_valid':excluded}

def tune(out,lower,selected_methods=METHODS):
    if set(selected_methods)!=set(METHODS):raise RuntimeError('all A0--A4 required before computing f')
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    lower=bounds(lower);entries=members('tuning');trials=[]
    with (out/'tuning_trials_raw.jsonl').open('x') as f:
        for method in selected_methods:
            for hidx,h in enumerate(HYPER[method]):
                values=[]
                for entry in entries:
                    for event in TUNING:
                        plant=Plant(Params(**entry['params']))
                        result=run_sequence(plant,event,method,h,seed=131+entry['index']*7+int(event[0][-1]))
                        val=official(entry,event,result)
                        values.append({'object':entry['index'],'event':event[0],
                                       'official':val,'round_curve':[(r['time_used_s'],r['normalized_error']) for r in result['iterations']],
                                       'best_iteration':result['best_iteration'],'valid_rounds':result['valid_rounds']})
                rec={'method':method,'candidate':hidx,'hyper':h,'cases':values}
                f.write(json.dumps(rec,allow_nan=False)+'\n');f.flush()
                trials.append(rec)
                print('PROGRESS',round(100*len(trials)/sum(len(HYPER[m]) for m in selected_methods)),method,hidx,flush=True)
    summary,provenance=reduce_trials(trials,lower)
    (out/'f_sources.json').write_text(json.dumps(provenance,indent=2,allow_nan=False))
    with (out/'tuning_trials.jsonl').open('x') as f:
        for rec in summary:f.write(json.dumps(rec,allow_nan=False)+'\n')
    chosen=[]
    for method in selected_methods:
        group=[r for r in summary if r['method']==method and r['median_S'] is not None]
        winner=min(group,key=lambda r:(r['median_S'],r['candidate'])) if group else None
        chosen.append({'method':method,'selected_candidate':None if winner is None else winner['candidate'],
                       'hyper':None if winner is None else winner['hyper'],
                       'median_S':None if winner is None else winner['median_S'],
                       'all_candidate_medians':[(r['candidate'],r['median_S']) for r in summary if r['method']==method]})
    (out/'selected_hyperparameters.json').write_text(json.dumps(chosen,indent=2,allow_nan=False))
    print('DONE',len(summary),len(provenance['excluded_no_valid']),flush=True)

def smoke_all(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    entry=members('tuning')[0];event=TUNING[0];result=[]
    for method in METHODS:
        r=run_sequence(Plant(Params(**entry['params'])),event,method,HYPER[method][0],seed=123)
        result.append({'method':method,'iterations':len(r['iterations']),
                       'total_time_s':r['total_time_s'],'valid_rounds':r['valid_rounds'],
                       'errors_by_iteration':[v['e'] for v in r['iterations']],
                       'best_iteration':r['best_iteration']})
        print('SMOKE',method,len(r['iterations']),r['total_time_s'],r['valid_rounds'],flush=True)
    (out/'smoke_all.json').write_text(json.dumps(result,indent=2,allow_nan=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--lower');ap.add_argument('--smoke-all',action='store_true');ap.add_argument('--methods',nargs='+',choices=METHODS,default=list(METHODS));a=ap.parse_args()
    if a.smoke_all:smoke_all(a.out)
    else:
        if not a.lower:ap.error('--lower required')
        tune(a.out,a.lower,a.methods)
