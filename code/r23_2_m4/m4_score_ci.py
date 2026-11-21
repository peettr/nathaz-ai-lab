#!/usr/bin/env python3
"""Post-hoc paired day-block intervals for M4 secondary scores; never refit models.
Inputs are frozen test-pair parquets from pairs/checkpoint_gfs_pairs_v3 parts.
The original score and its preregistered D(L) are not changed.
"""
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

LEADS=(10,20,30,60,120,180,240,300,360)
METHODS=('P','F','B')
METRICS=('auc','topk_rows_1','topk_events_1','topk_rows_5','topk_events_5','topk_rows_10','topk_events_10')

def evaluate(label, event, score, weight, day, fractions):
    """Weighted bootstrap copies of whole UTC issue days, exact weighted AUC/top-k.
    Event IDs remain those frozen from the full observed sequence; a repeated
    day does not create an additional independent event. This respects the
    original scorer's event denominator even across adjacent UTC days.
    """
    N=int(weight.sum()); positive=int(np.dot(weight,label))
    if not N or not positive or positive==N: return None
    auc=float(roc_auc_score(label, score, sample_weight=weight))
    order=np.argsort(score)[::-1]  # identical score rank convention to m4_score.py
    w=weight[order]; y=label[order]; e=event[order]; d=day[order]
    # By replication order each row's copies are adjacent. At a boundary a
    # partial copy of an identical row is immaterial for row or event hits.
    cum=np.cumsum(w); output={'auc':auc}
    total_events=len(set(e[(y==1)&(w>0)]))
    for frac,tag in zip(fractions,('1','5','10')):
        k=max(1,math.ceil(N*frac))
        alarms=np.clip(k-(cum-w),0,w)
        output[f'topk_rows_{tag}']=float(np.dot(alarms,y)/positive)
        captured=set(e[(y==1)&(alarms>0)])
        output[f'topk_events_{tag}']=len(captured)/total_events
    return output

def run(pairs, original, config, out):
    cfg=json.loads(Path(config).read_text()); n=cfg['bootstrap_days']; seed=cfg['bootstrap_seed']
    if n!=1000 or seed!=230202 or cfg['top_k']!=[.01,.05,.1]: raise ValueError('configuration mismatch')
    table=[]; changes=[]
    for net in ('OKC','Swiss'):
        df=pd.read_parquet(Path(pairs)/f'{net}_GFS_test_delay4.parquet')
        published=pd.read_csv(Path(original)/f'{net}_GFS_delay4_secondary.csv')
        for lead in LEADS:
            g=df[df.lead_min==lead].reset_index(drop=True)
            days=pd.to_datetime(g.issue_utc,utc=True).dt.date.to_numpy()
            unique,day_id=np.unique(days,return_inverse=True)
            label=g.strong.astype(int).to_numpy();event=g.event_id.to_numpy()
            if np.any((label==1)&(event<0)):raise ValueError('strong event unmapped')
            # Assert exact original full-sample point scores before resampling.
            scores={m:g[m].to_numpy(float) for m in METHODS}
            observed={m:evaluate(label,event,scores[m],np.ones(len(g),dtype=np.int32),day_id,cfg['top_k']) for m in METHODS}
            for m in METHODS:
                for frac,tag in zip(cfg['top_k'],('1','5','10')):
                    r=published[(published.lead_min==lead)&(published.method==m)&(published.metric=='auc_topk')&np.isclose(published.k_fraction,frac)].iloc[0]
                    for key,col in [('auc','auc'),(f'topk_rows_{tag}','topk_rows'),(f'topk_events_{tag}','topk_events')]:
                        if not np.isclose(observed[m][key],r[col],atol=1e-12):raise AssertionError((net,lead,m,key,observed[m][key],r[col]))
            print('verified',net,lead,len(g),'days',len(unique),flush=True)
            rng=np.random.default_rng(seed+lead+4*10000)
            repl={m:{k:[] for k in METRICS} for m in METHODS}
            delta={base:{metric:[] for metric in ('mae',)+METRICS} for base in ('P','F')}
            errs={m:np.abs(g.obs.to_numpy(float)-scores[m]) for m in METHODS}
            for i in range(n):
                draw=rng.integers(0,len(unique),size=len(unique))
                counts=np.bincount(draw,minlength=len(unique))
                weight=counts[day_id].astype(np.int32)
                stats={m:evaluate(label,event,scores[m],weight,day_id,cfg['top_k']) for m in METHODS}
                if any(s is None for s in stats.values()):raise ValueError((net,lead,i,'single class'))
                for m in METHODS:
                    for metric in METRICS:repl[m][metric].append(stats[m][metric])
                for base in ('P','F'):
                    delta[base]['mae'].append(float(np.dot(weight,errs['B']-errs[base])/weight.sum()))
                    for metric in METRICS:delta[base][metric].append(stats['B'][metric]-stats[base][metric])
                if (i+1)%200==0:print('draw',net,lead,i+1,flush=True)
            for m in METHODS:
                for metric in METRICS:
                    lo,hi=np.quantile(repl[m][metric],[.025,.975]);table.append(dict(network=net,lead_min=lead,method=m,metric=metric,point=observed[m][metric],lo=lo,hi=hi,n=len(g),days=len(unique),replicates=n))
            for base in ('P','F'):
                for metric in ('mae',)+METRICS:
                    point=float(np.mean(errs['B']-errs[base])) if metric=='mae' else observed['B'][metric]-observed[base][metric]
                    lo,hi=np.quantile(delta[base][metric],[.025,.975]);changes.append(dict(network=net,lead_min=lead,contrast=f'B-{base}',metric=metric,point=point,lo=lo,hi=hi,n=len(g),days=len(unique),replicates=n))
    assert len(table)==2*9*3*7 and len(changes)==2*9*2*8
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    pd.DataFrame(table).to_csv(out/'secondary_ci.csv',index=False)
    pd.DataFrame(changes).to_csv(out/'increment_ci.csv',index=False)
    (out/'summary.json').write_text(json.dumps(dict(secondary_rows=len(table),increment_rows=len(changes),bootstrap_days=n,bootstrap_seed=seed,paired=True),indent=2))
    print('DONE',len(table),len(changes),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for x in ('pairs','original','config','out'):ap.add_argument('--'+x,required=True)
    a=ap.parse_args();run(a.pairs,a.original,a.config,a.out)
