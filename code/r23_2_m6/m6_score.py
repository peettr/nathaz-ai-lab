#!/usr/bin/env python3
"""M6 frozen scorer: train/test split, latest usable GFS, LOSO, UTC-day bootstrap.
Runs only on Colab CPU. No test rows opened in 'train' mode.
"""
import json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import hypergeom
from sklearn.metrics import roc_auc_score
ROOT=Path('/content/m6'); CFG=json.loads((ROOT/'config.json').read_text()); OUT=ROOT/'output_final'; OUT.mkdir(exist_ok=True)
LEADS=CFG['leads_min']; TAUS=CFG['taus_min']; TERRAIN=CFG['terrain_classes']
SITES=json.loads((ROOT/'stations.json').read_text()); NAMES=sorted(s['site'] for s in SITES)
STATIC={s['site']:s for s in SITES}; BOUND=pd.Timestamp('2024-01-01',tz='UTC')
METHODS=('P','R','F','F_D','B','B_D','T0','D2','B_R','B_T0','B_D2')


def observations(start,end):
    paths=sorted((ROOT/'obs').glob('obs_*.csv'))
    if len(paths)!=12:raise ValueError('12 observation files required')
    d=pd.concat((pd.read_csv(p,usecols=['station','time_utc','speed_ms']) for p in paths),ignore_index=True)
    d=d.rename(columns={'station':'site','time_utc':'valid_end_utc','speed_ms':'obs'})
    d.valid_end_utc=pd.to_datetime(d.valid_end_utc,utc=True)
    d=d[(d.valid_end_utc>=start)&(d.valid_end_utc<end)].dropna(subset=['obs'])
    if set(d.site)!=set(NAMES):raise ValueError('observation roster mismatch')
    if d.duplicated(['site','valid_end_utc']).any():raise ValueError('duplicate observation timestamps')
    return d.set_index(['site','valid_end_utc']).obs.sort_index()


def forecast(stage):
    paths=sorted((ROOT/f'{stage}_gfs').glob('*.csv'))
    if len(paths)<350:raise ValueError(f'incomplete {stage} GFS {len(paths)}')
    d=pd.concat((pd.read_csv(p) for p in paths),ignore_index=True)
    d.init_utc=pd.to_datetime(d.init_utc,utc=True)
    if d.duplicated(['site','init_utc','fhr']).any():raise ValueError('duplicate model grid outputs')
    if set(d.site)!=set(NAMES) or not set(range(19))<=set(d.fhr):raise ValueError('incomplete fields')
    return {(s,t,int(h)):(float(u),float(v),float(eu),float(ev),float(z),float(dz)) for s,t,h,u,v,eu,ev,z,dz in d[['site','init_utc','fhr','u','v','eu','ev','z_model_sfc','dz']].itertuples(index=False,name=None)}


def construct(obs,fc,stage,delay):
    lo=pd.Timestamp(CFG[f'{stage}_start']);hi=pd.Timestamp(CFG[f'{stage}_end'])
    if stage=='train':hi=BOUND-pd.Timedelta(hours=6)
    issues=pd.date_range(lo,hi,freq='h',inclusive='left')
    rows=[];missing=0
    for site in NAMES:
        for issue in issues:
            p=obs.get((site,issue),np.nan)
            if not np.isfinite(p):continue
            init=(issue-pd.Timedelta(hours=delay)).floor('6h')
            if init+pd.Timedelta(hours=delay)>issue:raise ValueError('GFS future issuance')
            for lead in LEADS:
                valid=issue+pd.Timedelta(minutes=lead)
                if stage=='train' and valid>=BOUND:continue
                y=obs.get((site,valid),np.nan)
                if not np.isfinite(y):continue
                mid=valid-pd.Timedelta(minutes=5)
                h0=int((mid-init).total_seconds()//3600);h1=h0+1
                if h0<0 or h1>18:continue
                try:a=np.asarray(fc[site,init,h0]);b=np.asarray(fc[site,init,h1])
                except KeyError:missing+=1;continue
                alpha=(mid-(init+pd.Timedelta(hours=h0))).total_seconds()/3600
                v=a*(1-alpha)+b*alpha
                r=float(math.hypot(v[0],v[1]));v1=float(math.hypot(v[2],v[3]))
                age=(mid-init).total_seconds()/3600;bucket=0 if age<=6 else 1 if age<=12 else 2
                rows.append((site,issue,init,valid,lead,float(y),float(p),r,v1,float(v[5]),bucket,STATIC[site]['terrain'],issue))
    cols=['site','issue_utc','init_utc','valid_end_utc','lead_min','obs','P','R','V1','dz','bucket','terrain','p_observed_utc']
    d=pd.DataFrame(rows,columns=cols)
    if d.empty:raise ValueError('no paired rows')
    guard(d,delay,stage)
    print('PAIRS',stage,delay,len(d),'missing_outputs',missing,flush=True)
    return d


def guard(d,delay,stage):
    if (d.init_utc+pd.Timedelta(hours=delay)>d.issue_utc).any():raise ValueError('init+delay > issue')
    if (d.p_observed_utc>d.issue_utc).any():raise ValueError('persistence uses future observation')
    if (d.valid_end_utc-d.issue_utc!=pd.to_timedelta(d.lead_min,unit='m')).any():raise ValueError('lead mismatch')
    if stage=='train' and ((d.valid_end_utc>=BOUND)|(d.issue_utc>=BOUND-pd.Timedelta(hours=6))).any():raise ValueError('train boundary')
    if stage=='test' and (d.issue_utc<BOUND).any():raise ValueError('test boundary')
    # The true input timestamps, not an assigned issue-time surrogate, determine cutoff.
    cutoff=pd.concat([d.init_utc+pd.Timedelta(hours=delay),d.p_observed_utc],axis=1).max(axis=1)
    if (cutoff>d.issue_utc).any():raise ValueError('info_cutoff_utc exceeds issue_utc')
    d['info_cutoff_utc']=cutoff


def design(d,method):
    r=d.R.to_numpy();v=d.V1.to_numpy();dz=d.dz.to_numpy()
    if method in ('F','T0'):return np.column_stack([np.ones(len(d)),r])
    if method=='F_D':return np.column_stack([np.ones(len(d)),r,v])
    if method=='D2':return np.column_stack([r,v,dz,r*dz,*[(d.terrain==x).to_numpy(float) for x in TERRAIN]])
    raise ValueError(method)


def fit(train):
    model={'coefs':{},'tau':{},'residuals':{},'threshold':{},'skipped_buckets':[]}
    # Only a globally empty bucket is structurally unavailable under this delay.
    structural_empty={b for b in (0,1,2) if not (train.bucket==b).any()}
    for site in NAMES:
        own=train[train.site==site];pool=train[train.site!=site]
        for b in (0,1,2):
            for typ,df in [('F',own),('F_D',own),('T0',pool),('D2',pool)]:
                g=df[df.bucket==b]
                if b in structural_empty:
                    model['skipped_buckets'].append(dict(site=site,bucket=b,method=typ,reason='structurally_empty_for_delay'))
                    continue
                if len(g)<CFG['min_train_pairs_per_fold']:raise ValueError(f'insufficient fit {site} {b} {typ}: {len(g)}')
                x=design(g,typ);c=np.linalg.lstsq(x,g.obs.to_numpy(),rcond=None)[0]
                model['coefs'][f'{site}:{b}:{typ}']=c.tolist()
        for typ,x,pairs in [('B','F',own),('B_D','F_D',own),('B_R','R',pool),('B_T0','T0',pool),('B_D2','D2',pool)]:
            yy=pairs.obs.to_numpy();pp=pairs.P.to_numpy();ll=pairs.lead_min.to_numpy()
            xx=(pairs.R.to_numpy() if x=='R' else predict_one(pairs,x,model,fit_site=site))
            loss={tau:float(np.abs(yy-(np.exp(-ll/tau)*pp+(1-np.exp(-ll/tau))*xx)).mean()) for tau in TAUS}
            model['tau'][f'{site}:{typ}']=min(loss,key=loss.get)
        for typ,pairs in [('B',own),('B_D',own),('B_D2',pool)]:
            pred=predict_one(pairs,typ,model,fit_site=site)
            for lead in LEADS:
                mask=(pairs.lead_min==lead).to_numpy();res=pairs.obs.to_numpy()[mask]-pred[mask]
                if len(res)<30:raise ValueError('too few residual samples')
                model['residuals'][f'{site}:{typ}:{lead}']=np.quantile(res,[.05,.1,.9,.95]).tolist()
    print('FIT_DONE',len(model['coefs']),len(model['tau']),flush=True)
    return model


def predict_one(df,typ,model,fit_site=None):
    if typ=='R':return df.R.to_numpy(float)
    if typ=='P':return df.P.to_numpy(float)
    if typ in ('F','F_D','T0','D2'):
        out=np.empty(len(df)); x=design(df,typ)
        for (site,b),ids in df.groupby(['site','bucket']).indices.items():
            key=f'{fit_site or site}:{b}:{typ}'
            if key not in model['coefs']:
                raise ValueError(f'unfitted bucket in prediction: {key}; no fallback')
            out[ids]=x[ids]@np.array(model['coefs'][key])
        return out
    base={'B':'F','B_D':'F_D','B_R':'R','B_T0':'T0','B_D2':'D2'}[typ]
    xx=predict_one(df,base,model,fit_site=fit_site);out=np.empty(len(df));p=df.P.to_numpy();ll=df.lead_min.to_numpy()
    for site,ids in df.groupby('site').indices.items():
        tau=model['tau'][f'{fit_site or site}:{typ}'];w=np.exp(-ll[ids]/tau);out[ids]=w*p[ids]+(1-w)*xx[ids]
    return out


def attach(d,model):
    d=d.copy()
    for method in METHODS:d[method]=predict_one(d,method,model)
    for typ in ('B','B_D','B_D2'):
        q=np.asarray([model['residuals'][f'{site}:{typ}:{lead}'] for site,lead in zip(d.site,d.lead_min)])
        for j,label in enumerate(('q05','q10','q90','q95')):d[f'{typ}_{label}']=d[typ].to_numpy()+q[:,j]
    return d


def add_events(d,obs,threshold):
    event_id={};next_id=0
    for site in NAMES:
        series=obs.xs(site,level=0).sort_index();previous=None
        for t in series[series>=threshold[site]].index:
            if previous is None or t-previous>pd.Timedelta(minutes=30):next_id+=1
            event_id[site,t]=next_id;previous=t
    d=d.copy();d['threshold_p95']=d.site.map(threshold)
    d['strong']=d.obs>=d.threshold_p95
    d['event_id']=[event_id.get((s,t),-1) for s,t in zip(d.site,d.valid_end_utc)]
    if (d.loc[d.strong,'event_id']<0).any():raise ValueError('unmapped strong event')
    return d


def aggregate(d,lead,delay,draws=True):
    g=d[d.lead_min==lead].copy();n=len(g);dates=g.issue_utc.dt.date.to_numpy();days=np.unique(dates)
    if len(days)<30:raise ValueError('too few test days')
    errors=np.column_stack([np.abs(g[m].to_numpy()-g.obs.to_numpy()) for m in METHODS]);counts=np.array([(dates==day).sum() for day in days])
    sums=np.array([errors[dates==day].sum(axis=0) for day in days]);mae=errors.mean(axis=0)
    idx=np.random.default_rng(CFG['bootstrap_seed']+lead+delay*10000).integers(0,len(days),(CFG['bootstrap_days'],len(days)))
    bm=sums[idx].sum(axis=1)/counts[idx].sum(axis=1)[:,None]
    series={m:(mae[i],bm[:,i]) for i,m in enumerate(METHODS)}
    def metric(name,point,bootstrap):return dict(delay_h=delay,lead_min=lead,metric=name,point=float(point),lo=float(np.quantile(bootstrap,.025)),hi=float(np.quantile(bootstrap,.975)),n=n,days=len(days))
    out=[metric('MAE_'+m,*series[m]) for m in METHODS]
    for name,num,den in [('A','B_D','B'),('B','B_D2',None)]:
        if den:
            v=(series[num][0]-series[den][0])/series[den][0];b=(series[num][1]-series[den][1])/series[den][1]
        else:
            v=(series[num][0]-min(series['B_R'][0],series['B_T0'][0]))/min(series['B_R'][0],series['B_T0'][0])
            base=np.minimum(series['B_R'][1],series['B_T0'][1]);b=(series[num][1]-base)/base
        out.append(metric('D_'+name,v,b))
    edges=[('R','F'),('F','F_D'),('F','B'),('F_D','B_D'),('B','B_D'),('R','T0'),('R','D2'),('T0','D2'),('B_R','B_D2'),('B_T0','B_D2')]
    for a,b in edges:out.append(metric('delta_MAE_'+a+'_to_'+b,series[b][0]-series[a][0],series[b][1]-series[a][1]))
    return out


def secondary(d,delay):
    rows=[];by_site=[];coverage=[];topk=[]
    for lead,g in d.groupby('lead_min'):
        for site,h in g.groupby('site'):
            row=dict(delay_h=delay,lead_min=int(lead),site=site,terrain=STATIC[site]['terrain'],dz_positive=bool(h.dz.mean()>0),n=len(h))
            for m in METHODS:row['MAE_'+m]=float(np.abs(h.obs-h[m]).mean())
            for m in METHODS:
                if h.strong.nunique()==2:row['AUC_'+m]=float(roc_auc_score(h.strong,h[m]))
                else:row['AUC_'+m]=np.nan
            by_site.append(row)
        if delay!=4:continue
        dates=g.issue_utc.dt.date.to_numpy();days=np.unique(dates);rng=np.random.default_rng(CFG['bootstrap_seed']+lead+40000)
        indices=[np.flatnonzero(dates==day) for day in days]
        draw=[np.concatenate([indices[i] for i in rng.integers(0,len(days),len(days))]) for _ in range(CFG['bootstrap_days'])]
        y=g.strong.to_numpy(bool); draw_auc={}; draw_topk={}
        for m in METHODS:
            pred=g[m].to_numpy();aucs=[];site_auc=[]
            for site,h in g.groupby('site'):
                if h.strong.nunique()==2:site_auc.append(roc_auc_score(h.strong,h[m]))
            for ix in draw:
                if np.unique(y[ix]).size==2:aucs.append(roc_auc_score(y[ix],pred[ix]))
            if len(site_auc)!=12:raise ValueError(f'site AUC undefined {lead} {m}')
            draw_auc[m]=np.asarray(aucs)
            rows.append(dict(delay_h=delay,lead_min=int(lead),method=m,metric='AUC_pooled',point=float(roc_auc_score(y,pred)),lo=float(np.quantile(aucs,.025)),hi=float(np.quantile(aucs,.975))))
            site_draw=[]
            for ix in draw[:CFG['bootstrap_days']]:
                sub=g.iloc[ix];vals=[]
                for site,h in sub.groupby('site'):
                    if h.strong.nunique()==2:vals.append(roc_auc_score(h.strong,h[m]))
                if len(vals)==12:site_draw.append(np.mean(vals))
            rows.append(dict(delay_h=delay,lead_min=int(lead),method=m,metric='AUC_site_mean',point=float(np.mean(site_auc)),lo=float(np.quantile(site_draw,.025)) if site_draw else np.nan,hi=float(np.quantile(site_draw,.975)) if site_draw else np.nan))
            for k in (.01,.05,.10):
                order=np.argsort(-pred,kind='stable');kk=max(1,math.ceil(len(g)*k));alarm=np.zeros(len(g),bool);alarm[order[:kk]]=True
                strong=g.loc[g.strong,['event_id']].copy();strong['alarm']=alarm[y]
                events=strong.groupby('event_id').alarm
                sizes=events.size().to_numpy()
                # exact hypergeometric random expectation per observed event size
                point_rows=float((alarm&y).sum()/y.sum());point_events=float(events.any().mean())
                exp_ev=float(np.mean(hypergeom.sf(0,len(g),sizes,kk)))
                vals_r=[];vals_e=[]
                for ix in draw:
                    yy=y[ix];n=len(ix);order2=np.argsort(-pred[ix],kind='stable');kk2=max(1,math.ceil(n*k));aa=np.zeros(n,bool);aa[order2[:kk2]]=True
                    vals_r.append(float((aa&yy).sum()/yy.sum()) if yy.sum() else np.nan)
                    ids=g.event_id.to_numpy()[ix];ss=pd.DataFrame({'event':ids[yy],'alarm':aa[yy]});vals_e.append(float(ss.groupby('event').alarm.any().mean()) if len(ss) else np.nan)
                draw_topk[m,k]=(np.asarray(vals_r),np.asarray(vals_e))
                topk.append(dict(delay_h=delay,lead_min=int(lead),method=m,k=k,rows=point_rows,rows_lo=np.nanquantile(vals_r,.025),rows_hi=np.nanquantile(vals_r,.975),events=point_events,events_lo=np.nanquantile(vals_e,.025),events_hi=np.nanquantile(vals_e,.975),random_rows=kk/len(g),random_events=exp_ev,n_events=len(sizes)))
        edges=[('R','F'),('F','F_D'),('F','B'),('F_D','B_D'),('B','B_D'),('R','T0'),('R','D2'),('T0','D2'),('B_R','B_D2'),('B_T0','B_D2')]
        for a,b in edges:
            if len(draw_auc[a])!=len(draw) or len(draw_auc[b])!=len(draw):raise ValueError('AUC resample class missing')
            auc_diff=draw_auc[b]-draw_auc[a]
            rows.append(dict(delay_h=delay,lead_min=int(lead),method=a+'_to_'+b,metric='delta_AUC_pooled',point=float(roc_auc_score(y,g[b])-roc_auc_score(y,g[a])),lo=float(np.quantile(auc_diff,.025)),hi=float(np.quantile(auc_diff,.975))))
            for k in (.01,.05,.10):
                old=next(t for t in topk if t['lead_min']==lead and t['method']==a and t['k']==k)
                new=next(t for t in topk if t['lead_min']==lead and t['method']==b and t['k']==k)
                row_delta=draw_topk[b,k][0]-draw_topk[a,k][0]
                event_delta=draw_topk[b,k][1]-draw_topk[a,k][1]
                topk.append(dict(delay_h=delay,lead_min=int(lead),method=a+'_to_'+b,k=k,rows=new['rows']-old['rows'],rows_lo=float(np.nanquantile(row_delta,.025)),rows_hi=float(np.nanquantile(row_delta,.975)),events=new['events']-old['events'],events_lo=float(np.nanquantile(event_delta,.025)),events_hi=float(np.nanquantile(event_delta,.975)),random_rows=np.nan,random_events=np.nan,n_events=new['n_events']))
        for typ in ('B','B_D','B_D2'):
            for key,h in [('all',g)]+[(site,t) for site,t in g.groupby('site')]:
                for nominal,lo,hi in [(90,'q05','q95'),(80,'q10','q90')]:
                    coverage.append(dict(delay_h=delay,lead_min=int(lead),site=key,method=typ,nominal=nominal,coverage=float(((h.obs>=h[f'{typ}_{lo}'])&(h.obs<=h[f'{typ}_{hi}'])).mean()),n=len(h),hazard='nonconvective_assumed'))
    pd.DataFrame(rows).to_csv(OUT/f'secondary_auc_delay{delay}.csv',index=False)
    pd.DataFrame(by_site).to_csv(OUT/f'by_site_delay{delay}.csv',index=False)
    pd.DataFrame(coverage).to_csv(OUT/f'coverage_delay{delay}.csv',index=False)
    pd.DataFrame(topk).to_csv(OUT/f'topk_delay{delay}.csv',index=False)


def run_train():
    obs=observations(pd.Timestamp(CFG['train_start']),BOUND)
    thresh={s:float(obs.xs(s).quantile(.95)) for s in NAMES}
    fc=forecast('train');all_models={};row_counts={}
    for delay in CFG['delays_h']:
        d=construct(obs,fc,'train',delay)
        if d.valid_end_utc.max()>=BOUND or d.issue_utc.max()>=BOUND-pd.Timedelta(hours=6):raise ValueError('training leakage')
        model=fit(d);model['threshold']=thresh;all_models[str(delay)]=model
        row_counts[str(delay)]=len(d)
        d.to_parquet(ROOT/f'train_pairs_delay{delay}.parquet',index=False)
    (ROOT/'models.json').write_text(json.dumps(all_models))
    (ROOT/'train_summary.json').write_text(json.dumps({'rows':row_counts,'threshold':thresh}))
    print('TRAIN_DONE',row_counts,flush=True)


def run_test():
    models=json.loads((ROOT/'models.json').read_text())
    obs=observations(BOUND,pd.Timestamp(CFG['test_end']))
    fc=forecast('test')
    main=[];gates=[]
    for delay in CFG['delays_h']:
        train=pd.read_parquet(ROOT/f'train_pairs_delay{delay}.parquet')
        train.issue_utc=pd.to_datetime(train.issue_utc,utc=True);train.valid_end_utc=pd.to_datetime(train.valid_end_utc,utc=True)
        d=construct(obs,fc,'test',delay)
        if train.valid_end_utc.max()>=d.issue_utc.min():raise ValueError('train valid_end overlaps test issue')
        d=attach(d,models[str(delay)]);d=add_events(d,obs,models[str(delay)]['threshold'])
        d.to_parquet(ROOT/f'test_predictions_delay{delay}.parquet',index=False)
        for lead in LEADS:main+=aggregate(d,lead,delay)
        current=pd.DataFrame(main);current.to_csv(OUT/'main.csv',index=False)
        if delay==4:
            x=current[(current.delay_h==4)&current.metric.isin(['D_A','D_B'])]
            if len(x)!=18:raise ValueError('missing lead in gate')
            gates=x[['lead_min','metric','point','lo','hi']].to_dict('records')
            stop=bool((x.hi>=0).all());(OUT/'gate.json').write_text(json.dumps({'stop':stop,'A_pass':bool((x[x.metric=='D_A'].hi<0).any()),'B_pass':bool((x[x.metric=='D_B'].hi<0).any()),'rows':gates},indent=2))
            print('M6_GATE',stop,flush=True)
            if stop:break
            secondary(d,delay)
        print('TEST_DELAY_DONE',delay,len(d),flush=True)
    if not gates:raise ValueError('no primary gate')
    print('TEST_DONE',flush=True)

if __name__=='__main__':{'train':run_train,'test':run_test}[sys.argv[1]]()
