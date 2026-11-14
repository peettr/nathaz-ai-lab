#!/usr/bin/env python3
"""Frozen R23.7 scorer. Six-arm 2023 holdout; never fit on 2023 observations."""
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import rankdata
SOURCES=['GRAP_v100_GFS','GRAP_v100_IFS','PANG_v100_GFS','PANG_v100_IFS','GFS','HRES']
FIVE=SOURCES[:-1]
KEY=['station','init_utc','lead_h']
SEED=20261108

def linear(x,y):
    m=np.isfinite(x)&np.isfinite(y);x=x[m];y=y[m]
    if len(x)<12:return (float(y.mean()),0.) if len(x) else (np.nan,np.nan)
    if np.std(x)<1e-8:return float(y.mean()),0.
    b,a=np.polyfit(x,y,1);return float(a),float(b)

def logistic(x,y):
    m=np.isfinite(x)&np.isfinite(y);x=x[m];y=y[m]
    if len(x)<30 or y.sum() in (0,len(y)):
        return 0.,float(np.log((y.sum()+.5)/(len(y)-y.sum()+.5)))
    mu=x.mean();sd=max(x.std(),.1);xx=(x-mu)/sd
    def loss(c):
        z=c[0]+c[1]*xx
        return np.logaddexp(0,z).sum()-(y*z).sum()+.01*c[1]**2
    r=minimize(loss,[float(np.log((y.mean()+.001)/(1-y.mean()+.001))),0.],method='BFGS')
    return float(r.x[1]/sd),float(r.x[0]-r.x[1]*mu/sd)

def read(path):
    a=pd.read_csv(path)
    a['init_utc']=pd.to_datetime(a.init_utc,utc=True,format='mixed')
    a['valid_utc']=a.init_utc+pd.to_timedelta(a.lead_h,unit='h')
    assert not a.duplicated(KEY+['source']).any(),path
    a['raw_speed']=np.hypot(a.fc_u,a.fc_v)
    return a

def intersect(df,sources):
    a=df[df.source.isin(sources)].copy()
    assert set(a.source)==set(sources),(set(a.source),sources)
    n=a.groupby(KEY).source.nunique(); keys=n[n.eq(len(sources))].index
    a=a.set_index(KEY).loc[keys].reset_index()
    assert a.source.value_counts().nunique()==1
    return a

def prepare(oldtrain,oldtest,train_new,test_new):
    oldtr=read(oldtrain);oldte=read(oldtest)
    train=pd.concat([oldtr[oldtr.source.isin(['GRAP_v100_GFS','PANG_v100_GFS','GFS'])]]+[read(p) for p in train_new],ignore_index=True)
    test=pd.concat([oldte[oldte.source.isin(['GRAP_v100_GFS','PANG_v100_GFS','GFS'])]]+[read(p) for p in test_new],ignore_index=True)
    assert set(train.source)==set(SOURCES) and set(test.source)==set(SOURCES)
    # One missing PG·IFS 2022 initialization is excluded from ALL arms before fitting.
    train=intersect(train,SOURCES)
    assert not train.init_utc.eq(pd.Timestamp('2022-12-01',tz='UTC')).any()
    obs=oldtr[oldtr.source.eq('GFS')][KEY+['metar_speed']].drop_duplicates(KEY)
    train=train.drop(columns=['metar_speed'],errors='ignore').merge(obs,on=KEY,how='left',validate='many_to_one')
    train=train[train.valid_utc.dt.year.eq(2022)&train.lead_h.isin([24,48])&train.metar_speed.notna()].copy()
    assert train.source.value_counts().nunique()==1
    # Existing held-out METAR targets only; original R23.2a SRE summer exclusion.
    obs=oldte[oldte.source.eq('GFS')][KEY+['metar_speed']].drop_duplicates(KEY)
    test=test.drop(columns=['metar_speed'],errors='ignore').merge(obs,on=KEY,how='left',validate='many_to_one')
    sre=test.station.eq('SRE')&test.valid_utc.between('2023-06-01','2023-09-30 23:59:59.999999')
    test=test[~sre&test.valid_utc.dt.year.eq(2023)&test.lead_h.isin([24,48])&test.metar_speed.notna()].copy()
    coefficients={};probability={}
    for (station,lead,source),g in train.groupby(['station','lead_h','source']):
        key=(station,int(lead),source)
        coefficients[key]=linear(g.raw_speed.to_numpy(),g.metar_speed.to_numpy())
        a,b=coefficients[key]
        z=np.maximum(0,a+b*g.raw_speed.to_numpy())
        probability[key]=logistic(z,(g.metar_speed.to_numpy()>=8).astype(float))
    for frame in (train,test):
        frame['corrected']=np.nan;frame['prob8']=np.nan
        for (station,lead,source),g in frame.groupby(['station','lead_h','source']):
            key=(station,int(lead),source)
            if key not in coefficients:raise ValueError(f'No training coefficient {key}')
            a,b=coefficients[key];z=np.maximum(0,a+b*g.raw_speed.to_numpy())
            p,q=probability[key]
            frame.loc[g.index,'corrected']=z
            frame.loc[g.index,'prob8']=expit(q+p*z)
    assert train.corrected.notna().all() and test.corrected.notna().all()
    return train,test,coefficients,probability

def verdict(point,ci,delta):
    if ci[0]>0 and point>=delta:return '支持假设（本配置）'
    if ci[1]<delta:return '不支持（本配置）'
    return '分不出'

def cell(frame,sources,lead,variant,delta):
    a=intersect(frame[frame.lead_h.eq(lead)],sources)
    assert a.metar_speed.notna().all() and a.source.value_counts().nunique()==1
    a['err']=np.abs(a[variant]-a.metar_speed)
    a['day']=a.valid_utc.dt.floor('D')
    days=pd.Index(sorted(a.day.unique()));n=len(days)
    assert n>1
    sums=np.stack([a[a.source.eq(s)].groupby('day').err.sum().reindex(days,fill_value=0).to_numpy() for s in sources],axis=1)
    counts=np.stack([a[a.source.eq(s)].groupby('day').size().reindex(days,fill_value=0).to_numpy() for s in sources],axis=1)
    assert np.array_equal(counts,counts[:,[0]]) or np.all(counts==counts[:,[0]])
    def calc(weights):
        maes=(weights@sums)/(weights@counts)
        dgc=maes[...,0]/maes[...,1]-1;dpg=maes[...,2]/maes[...,3]-1
        c=dgc-dpg
        phys=maes[...,4]/maes[...,5]-1 if len(sources)==6 else None
        return maes,dgc,dpg,c,phys
    point=calc(np.ones(n));rng=np.random.default_rng(SEED)
    weights=rng.multinomial(n,np.full(n,1/n),size=1000)
    draws=calc(weights);ci=np.quantile(draws[3],[.025,.975]).tolist()
    def interval(x):return np.quantile(x,[.025,.975]).tolist()
    dgc=float(point[1]);dpg=float(point[2]);c=float(point[3]);phys=None if point[4] is None else float(point[4])
    return {'sample':'six_arm_from_2023_01_18' if len(sources)==6 else 'five_arm_full_year','lead_h':lead,'variant':variant,'delta':delta,'paired_keys':int(counts.sum(axis=0)[0]),'verification_days':n,'mae_mps':dict(zip(sources,map(float,point[0]))),'d_GC':dgc,'d_PG':dpg,'C':c,'C_ci95':ci,'d_GC_ci95':interval(draws[1]),'d_PG_ci95':interval(draws[2]),'d_phys':phys,'d_GC_minus_d_phys':None if phys is None else dgc-phys,'d_PG_minus_d_phys':None if phys is None else dpg-phys,'verdict':verdict(c,ci,delta),'reverse':bool(ci[1]<0),'seed':SEED,'draws':1000}

def descriptive(frame,sources,lead):
    a=intersect(frame[frame.lead_h.eq(lead)],sources)
    truth=a[a.source.eq(sources[0])][KEY+['metar_speed']]
    assert not truth.duplicated(KEY).any()
    event=(truth.metar_speed>=8).to_numpy();base=float(event.mean())
    out={'n':len(truth),'events':int(event.sum()),'event_rate':base,'arms':{}}
    for s in sources:
        g=a[a.source.eq(s)].merge(truth[KEY],on=KEY,validate='one_to_one').sort_values(KEY)
        t=truth.sort_values(KEY);assert np.array_equal(g[KEY].to_numpy(),t[KEY].to_numpy())
        y=(g.metar_speed.to_numpy()>=8);p=g.prob8.to_numpy()
        assert np.isfinite(p).all()
        bs=float(np.mean((p-y)**2));auc=None
        if y.sum() and (~y).sum():auc=float((rankdata(p)[y].sum()-y.sum()*(y.sum()+1)/2)/(y.sum()*(~y).sum()))
        top={}
        for k in (.01,.05,.10):
            nk=max(1,int(math.ceil(len(g)*k)))
            order=np.lexsort((g.station.to_numpy(),g.init_utc.astype('int64').to_numpy(),-p))
            hit=int(y[order[:nk]].sum())
            top[str(k)]={'selected':nk,'captured_events':hit,'capture_rate':float(hit/y.sum()) if y.sum() else None}
        out['arms'][s]={'brier':bs,'bss_vs_event_climatology':float(1-bs/(base*(1-base))) if 0<base<1 else None,'auc':auc,'top_k':top}
    return out

def main():
    ap=argparse.ArgumentParser()
    for x in ['old-train','old-test','train-gc','train-pg','train-hres','test-gc','test-pg','test-hres','output']:ap.add_argument('--'+x,required=True)
    a=ap.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    for name in ('metrics_v1.json','results_v1.md'):assert not (out/name).exists(),name
    train,test,coef,prob=prepare(a.old_train,a.old_test,[a.train_gc,a.train_pg,a.train_hres],[a.test_gc,a.test_pg,a.test_hres])
    six=test[test.init_utc.ge(pd.Timestamp('2023-01-18',tz='UTC'))].copy()
    cases=[]
    for sample,frame,sources in [('primary',six,SOURCES),('full_year_five',test,FIVE)]:
        for lead in (24,48):
            for variant in ('corrected','raw_speed'):
                for delta in (.01,.02,.03):cases.append({'cohort':sample,**cell(frame,sources,lead,variant,delta)})
    maincell=next(c for c in cases if c['cohort']=='primary' and c['lead_h']==24 and c['variant']=='corrected' and c['delta']==.02)
    rawcell=next(c for c in cases if c['cohort']=='primary' and c['lead_h']==24 and c['variant']=='raw_speed' and c['delta']==.02)
    conflict={maincell['verdict'],rawcell['verdict']}=={'支持假设（本配置）','不支持（本配置）'}
    overall='对订正敏感·分不出' if conflict else maincell['verdict']
    coverage={}
    for year,frame in [(2022,train),(2023,test)]:
        coverage[str(year)]={s:{str(lead):int(frame[frame.source.eq(s)&frame.lead_h.eq(lead)].init_utc.nunique()) for lead in (24,48)} for s in SOURCES}
    counts={'train_common_keys':len(train)//6,'train_removed_missing_pg_2022_12_01_00':'all arms at that initialization','test_five_observed_keys':len(intersect(test[test.lead_h.eq(24)],FIVE))//5,'test_six_observed_keys':maincell['paired_keys'],'test_six_earliest_valid':str(six.valid_utc.min()),'test_six_latest_valid':str(six.valid_utc.max())}
    description=descriptive(intersect(six[six.lead_h.eq(24)],SOURCES),SOURCES,24)
    payload={'overall_verdict':overall,'correction_conflict':conflict,'main':maincell,'raw_main':rawcell,'all_cells':cases,'descriptive_8mps':description,'coverage_in_observation_paired_table':coverage,'counts':counts,'protocol':'PREREG_R23.7.md sections 2-6','training_coefficients':{str(k):v for k,v in coef.items()},'publication_delay':'not accounted (R23.2a convention)','training_C22_known_pre_start':0.022,'training_C22_role':'power gate only; not used for verdict'}
    with (out/'metrics_v1.json').open('x') as f:json.dump(payload,f,indent=2,ensure_ascii=False,allow_nan=False)
    fmt=lambda v:'NA' if v is None else f'{v:.6f}'
    lines=['# R23.7 2023 检验结果（本配置）','',f'总判定：{overall}。订正冲突：{conflict}。','',f'训练年 C22 点估计 0.022 在开跑前已知，只用于分辨力闸，未用于本判定。发布延迟不计。',f'样本与剔除：{json.dumps(counts,ensure_ascii=False)}；取数与缺档逐对象见源账本。','', '|样本|h|版本|δ|配对|验证日|d_GC|d_PG|C|95% CI|d_phys|GC−phys|PG−phys|判定|反向|','|---|---:|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|']
    for c in cases:
        lines.append('|'+ '|'.join(str(x) for x in [c['cohort'],c['lead_h'],c['variant'],c['delta'],c['paired_keys'],c['verification_days'],fmt(c['d_GC']),fmt(c['d_PG']),fmt(c['C']),f"[{fmt(c['C_ci95'][0])}, {fmt(c['C_ci95'][1])}]",fmt(c['d_phys']),fmt(c['d_GC_minus_d_phys']),fmt(c['d_PG_minus_d_phys']),c['verdict'],c['reverse']])+'|')
    lines+=['','## ≥8 m/s 概率与排序（24 h 主样本，仅描述）',f"事件 {description['events']}/{description['n']}；BSS 相对样本事件气候率，AUC 为概率秩；Top-k 为选中前 k% 站点记录捕获的事件占全部事件比例。",'|臂|BSS|AUC|Top 1%|Top 5%|Top 10%|','|---|---:|---:|---:|---:|---:|']
    for s,r in description['arms'].items():lines.append('|'+ '|'.join([s,fmt(r['bss_vs_event_climatology']),fmt(r['auc'])]+[fmt(r['top_k'][str(k)]['capture_rate']) for k in (.01,.05,.10)])+'|')
    lines+=['','只限 OKC 周边 12 站、指定模式/初值与 2022→2023 训练检验配置；METAR 2 min 持续风，非阵风。所有订正及阈值概率参数仅从 2022 拟合；不产出区间预报，故灾种覆盖率不适用。']
    with (out/'results_v1.md').open('x') as f:f.write('\n'.join(lines)+'\n')
    print(json.dumps({'overall':overall,'counts':counts,'main':maincell,'raw_main':rawcell},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
