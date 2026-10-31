#!/usr/bin/env python3
"""Frozen-candidate M5 Swiss scorer. Run on Colab only after training and hash gate.
Input /content/m5/train_pairs.parquet and /content/m5/test_pairs.parquet.
"""
import json, math
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
ROOT=Path('/content/m5');OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
FHRS=(6,12,24,48);METHODS=('R','T0','D1','D2','M','M+D1')
TERRAIN=('ridge','pass','valley','plateau')

def guard(df,delay):
    for name in ('site','init_utc','issue_utc','valid_end_utc','info_cutoff_utc','fhr','raw','v1','dz','terrain','obs'):
        if name not in df:raise ValueError('missing '+name)
    init=pd.to_datetime(df.init_utc,utc=True);issue=pd.to_datetime(df.issue_utc,utc=True)
    cutoff=pd.to_datetime(df.info_cutoff_utc,utc=True)
    valid=pd.to_datetime(df.valid_end_utc,utc=True)
    if (cutoff>issue).any():raise ValueError('info cutoff exceeds issue')
    if (init+pd.Timedelta(hours=delay)>issue).any():raise ValueError('GFS is not yet available')
    if (valid<issue).any():raise ValueError('negative lead')
    if (valid-init!=pd.to_timedelta(df.fhr,unit='h')).any():raise ValueError('fhr mismatch')
    if (df.fhr<delay).any():raise ValueError('lead shorter than availability')

def design(df,method):
    raw=df.raw.to_numpy();v1=df.v1.to_numpy();dz=df.dz.to_numpy()
    if method in ('T0','M'):return np.column_stack((np.ones(len(df)),raw))
    if method=='D1':return np.column_stack((np.ones(len(df)),v1))
    if method=='M+D1':return np.column_stack((np.ones(len(df)),raw,v1))
    if method=='D2':return np.column_stack((np.ones(len(df)),raw,v1,dz,raw*dz,*[(df.terrain==x).to_numpy(dtype=float) for x in TERRAIN]))
    raise ValueError(method)

def predict(train,test):
    if set(train.site)!=set(test.site) or len(set(test.site))!=12:raise ValueError('site roster')
    train=train.copy();test=test.copy();pred=[];resid={};coeff=[]
    for fhr in FHRS:
        for site in sorted(test.site.unique()):
            own=train[(train.site==site)&(train.fhr==fhr)]
            pool=train[(train.site!=site)&(train.fhr==fhr)]
            part=test[(test.site==site)&(test.fhr==fhr)].copy()
            if len(own)<50 or len(pool)<500 or not len(part):raise ValueError('missing fold '+site+' '+str(fhr))
            part['R']=part.raw
            for method in METHODS[1:]:
                fit=own if method.startswith('M') else pool
                A=design(fit,method);B=design(part,method)
                c=np.linalg.lstsq(A,fit.obs.to_numpy(),rcond=None)[0]
                part[method]=B@c
                r=fit.obs.to_numpy()-A@c
                resid[(site,fhr,method)]=r
                coeff.append({'site':site,'fhr':fhr,'method':method,'n':len(fit),'coefficients':json.dumps(c.tolist())})
            # P95 of target site's TRAINING observations alone defines the event.
            part['threshold_p95']=np.quantile(own.obs,.95)
            for method in ('T0','D2','M'):
                r=resid[(site,fhr,method)]
                for q in (.05,.10,.50,.90,.95):part[f'{method}_q{int(q*100):02d}']=part[method]+np.quantile(r,q)
            pred.append(part)
    return pd.concat(pred,ignore_index=True),pd.DataFrame(coeff)

def auc(y,score):
    if len(np.unique(y))<2:return float('nan')
    return float(roc_auc_score(y,score))

def topk(frame,method,k):
    # stable tie ordering by site/init, identical across methods on a resample
    s=frame.sort_values([method,'site','init_utc'],ascending=[False,True,True],kind='mergesort')
    n=max(1,math.ceil(len(s)*k));den=frame.event.sum()
    return float(s.iloc[:n].event.sum()/den) if den else float('nan')

def scores(d):
    out={}
    for m in METHODS:
        out['MAE_'+m]=float(np.mean(np.abs(d[m]-d.obs)))
        out['AUC_'+m]=auc(d.event.to_numpy(),d[m].to_numpy())
        for k in (.01,.05,.10):out[f'Top{int(k*100)}_'+m]=topk(d,m,k)
    base=out['MAE_T0'];out['D']=(out['MAE_D2']-base)/base
    out['D1_T0']=(out['MAE_D1']-base)/base
    out['rho']=(base-out['MAE_D2'])/(base-out['MAE_M']) if abs(base-out['MAE_M'])>1e-12 else float('nan')
    out['M+D1_minus_M']=out['MAE_M+D1']-out['MAE_M']
    for a,b in (('R','T0'),('T0','D2'),('R','M'),('M','M+D1')):
        out[f'MAE_{a}_to_{b}']=out['MAE_'+b]-out['MAE_'+a]
        out[f'AUC_{a}_to_{b}']=out['AUC_'+b]-out['AUC_'+a]
        for k in (1,5,10):out[f'Top{k}_{a}_to_{b}']=out[f'Top{k}_'+b]-out[f'Top{k}_'+a]
    for m in ('T0','D2','M'):
        out['cover90_'+m]=float(((d.obs>=d[f'{m}_q05'])&(d.obs<=d[f'{m}_q95'])).mean())
        out['cover80_'+m]=float(((d.obs>=d[f'{m}_q10'])&(d.obs<=d[f'{m}_q90'])).mean())
    return out

def bootstrap(d,fhr,delay,n_draws=1000):
    d=d.copy();d['event']=d.obs>=d.threshold_p95
    d['day']=pd.to_datetime(d.valid_end_utc,utc=True).dt.floor('D')
    days=list(d.day.unique());byday={day:d[d.day==day] for day in days}
    if len(days)<30:raise ValueError('too few verifying days')
    point=scores(d)
    # Repeated days are entire network blocks; same draws for all methods and deltas.
    rng=np.random.default_rng(230503+fhr+delay*100)
    draws=[]
    for _ in range(n_draws):
        b=pd.concat([byday[days[i]] for i in rng.integers(0,len(days),len(days))],ignore_index=True)
        draws.append(scores(b))
    out=[]
    for metric,value in point.items():
        x=np.array([z[metric] for z in draws],dtype=float)
        x=x[np.isfinite(x)]
        out.append({'fhr':fhr,'delay_h':delay,'metric':metric,'point':value,'lo':float(np.quantile(x,.025)) if len(x) else np.nan,'hi':float(np.quantile(x,.975)) if len(x) else np.nan,'n':len(d),'days':len(days),'bootstrap_valid':len(x)})
    return out

def main():
    train=pd.read_parquet(ROOT/'train_pairs.parquet');test=pd.read_parquet(ROOT/'test_pairs.parquet')
    assert set(train.site)==set(test.site) and len(set(train.site))==12
    assert pd.to_datetime(train.valid_end_utc,utc=True).max()<pd.Timestamp('2024-01-01',tz='UTC')
    assert pd.to_datetime(test.valid_end_utc,utc=True).min()>=pd.Timestamp('2024-01-01',tz='UTC')
    for delay in (4,6):
        a,b=train.copy(),test.copy()
        for x in (a,b):
            x['issue_utc']=pd.to_datetime(x.init_utc,utc=True)+pd.Timedelta(hours=delay)
            x['info_cutoff_utc']=x.issue_utc
            guard(x,delay)
        pred,coef=predict(a,b)
        pred.to_parquet(OUT/f'swiss_predictions_delay{delay}.parquet',index=False)
        coef.to_csv(OUT/f'swiss_coefficients_delay{delay}.csv',index=False)
        if delay==4:
            strat=[]
            for (fhr,terrain),part in pred.groupby(['fhr','terrain']):
                item={'fhr':int(fhr),'terrain':terrain,'n':len(part),'sites':part.site.nunique()}
                item.update({f'MAE_{m}':float(np.mean(np.abs(part[m]-part.obs))) for m in METHODS})
                strat.append(item)
            pd.DataFrame(strat).to_csv(OUT/'swiss_terrain_mae.csv',index=False)
        summaries=[]
        for fhr in FHRS:
            frame=pred[pred.fhr==fhr]
            summaries.extend(bootstrap(frame,fhr,delay) if delay==4 else [dict(fhr=fhr,delay_h=delay,metric=k,point=v,lo=np.nan,hi=np.nan,n=len(frame)) for k,v in scores(frame.assign(event=frame.obs>=frame.threshold_p95)).items()])
        pd.DataFrame(summaries).to_csv(OUT/f'swiss_scores_delay{delay}.csv',index=False)
        if delay==4:
            gate=pd.DataFrame(summaries).query("metric == 'D'")
            stop=bool((gate.hi>=0).all());passed=bool((gate.hi<0).any())
            (OUT/'gate.json').write_text(json.dumps({'pass':passed,'stop':stop,'D':gate[['fhr','point','lo','hi']].to_dict('records')},indent=2))
            print('M5_GATE',passed,stop,flush=True)
            # A stop gate prohibits any expansion; delay-6 within same frozen method is reported only if allowed.
            if stop:break
    print('SCORE_DONE',flush=True)
if __name__=='__main__':main()
