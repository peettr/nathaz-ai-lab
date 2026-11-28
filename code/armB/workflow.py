"""Bounded single-submission arm-B workflow; tune only if migration and budget pass."""
import json,time,hashlib,traceback
from pathlib import Path
import numpy as np
from migration_gate import one
from method_g import (Params,Plant,TUNING,normalized,members,candidates,
                       run_sequence_g,official_g,SRC)
ROOT=Path(__file__).resolve().parent
CAP=8*3600

def save(path,obj):
    path=ROOT/path
    with path.open('x') as f:json.dump(obj,f,allow_nan=False,ensure_ascii=False,indent=2)
    return path

def main():
    t0=time.perf_counter();entries=members('tuning');hypers=candidates()
    assert len(entries)==8 and len(TUNING)==2 and len(hypers)==12
    with (ROOT/'results_gate.jsonl').open('x') as f:
        for entry in entries[:3]:
            for ev in TUNING:
                row=one(entry,ev,1e-4)
                row['pass']=all(row['diff'][k]['max_rel']<=v for k,v in [('u',.01),('Iu',.02),('Lux',.02)])
                f.write(json.dumps(row,allow_nan=False)+'\n');f.flush()
                print('GATE',row['object'],row['event'],row['pass'],
                      {k:round(row['diff'][k]['max_rel'],5) for k in ('u','Iu','Lux')},flush=True)
                if not row['pass']:
                    print('STOP migration failed; one human repair round permitted, not automatic resubmission',flush=True)
                    return 31
    entry=entries[0];ev=TUNING[0];h=hypers[0]
    tp=time.perf_counter();pilots=[]
    for j in range(2):
        seed=131+entry['index']*7+int(ev[0][-1])+(j*100000)
        pilots.append(run_sequence_g(Plant(Params(**entry['params'])),ev,h,seed=seed))
        print('PILOT',j+1,flush=True)
    pilot_time=time.perf_counter()-tp
    ts=time.perf_counter();off,which=official_g(entry,ev,pilots[0]);official_time=time.perf_counter()-ts
    ncases=len(hypers)*len(entries)*len(TUNING)*3
    scoring_cases=24*12*3  # post-freeze only; never run in this job
    per_case=pilot_time/2+official_time
    estimated=1.2*per_case*ncases
    # Gate/pilot time already spent; require full workflow below 8 core-hours.
    budget={'pilot_wall_s':pilot_time,'official_wall_s':official_time,
            'pilot_sequences':2,'pilot_rounds':50,'tuning_sequences':ncases,
            'scoring_sequences_estimate_only':scoring_cases,
            'formula':'1.2 * N_cases * (pilot_wall_s/2 + official_wall_s)',
            'estimated_tuning_core_hours':estimated/3600,
            'estimated_scoring_core_hours':1.2*per_case*scoring_cases/3600,
            'already_used_core_hours':(time.perf_counter()-t0)/3600,
            'limit_core_hours':8,
            'pilot_official_valid':None if off is None else off['valid']}
    save('budget.json',budget);print('BUDGET',json.dumps(budget),flush=True)
    if time.perf_counter()-t0+estimated>CAP:
        print('STOP budget forecast exceeds 8 core-hours; no tuning and no scoring set',flush=True)
        return 32
    frozen=json.loads((SRC/'q1/tuning_selected_11f.json').read_text())['f']
    cases=[]
    with (ROOT/'tuning_G.jsonl').open('x') as f:
        for i,hyper in enumerate(hypers):
            for entry in entries:
                for ev in TUNING:
                    for seed_no in (1,2,3):
                        if time.perf_counter()-t0>CAP-600:
                            print('STOP elapsed budget approaching cap; partial tuning invalid',flush=True)
                            return 33
                        seed=131+entry['index']*7+int(ev[0][-1])+(seed_no-1)*100000
                        seq=run_sequence_g(Plant(Params(**entry['params'])),ev,hyper,seed=seed)
                        score,chosen=official_g(entry,ev,seq)
                        if score is None or not score['valid']:
                            raise RuntimeError('official score invalid after initial fallback')
                        key=f"{entry['index']}/{ev[0]}"
                        delta=np.maximum(0,np.asarray(score['errors'])-np.asarray(frozen[key]))
                        row={'candidate':i,'hyper':hyper,'object':entry['index'],
                             'event':ev[0],'seed':seed_no,'errors':score['errors'],
                             'S':normalized(delta),'best_iteration':chosen,
                             'valid_rounds':seq['valid_rounds']}
                        f.write(json.dumps(row,allow_nan=False)+'\n');f.flush();cases.append(row)
                        print('TUNE',len(cases),'/',ncases,flush=True)
    candidates_stats=[]
    for i,hyper in enumerate(hypers):
        object_scores=[]
        for entry in entries:
            object_scores.append(float(np.mean([row['S'] for row in cases
                             if row['candidate']==i and row['object']==entry['index']])))
        candidates_stats.append({'candidate':i,'hyper':hyper,
             'object_scores':object_scores,'median_S':float(np.median(object_scores))})
    chosen=min(candidates_stats,key=lambda r:(r['median_S'],r['candidate']))
    save('tuning_summary.json',{'chosen':chosen,'candidates':candidates_stats,
        'cases':len(cases),'f_provenance':'frozen L30.1f tuning selected_11f.json',
        'scoring_set_run':False})
    card=ROOT/'METHOD_G_BASIS.md'
    with card.open('x') as f:f.write('# 方法 G 依据卡（调参集冻结）\n\n'
      '输入：L30.1f v8b 调参集 8 对象×2 事件×3 独立序列。'
      '每序列固定 25 轮及 2465 s；评分用冻结 numpy 官方评分函数。'
      'JAX 孪生使用 8 对象参数中位数、公共随机数、残差修正；'
      'Adam 的学习率、内步数和反传窗长仅在调参集选择。\n\n'
      f'候选 12 组的对象层 S 中位数见 tuning_summary.json；入选 {json.dumps(chosen,ensure_ascii=False)}。\n'
      '比较用 f 是 L30.1f 冻结调参 f；相减后截零。评分集未运行。\n')
    digest=hashlib.sha256(card.read_bytes()).hexdigest()
    print('FROZEN',card,str(digest),flush=True)
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:
        traceback.print_exc();raise
