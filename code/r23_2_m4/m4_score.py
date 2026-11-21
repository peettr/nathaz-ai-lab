#!/usr/bin/env python3
"""Frozen M4 deterministic scoring. Run only on Colab CPU after hashes are carded.
Inputs: /content/m4/<network>/obs_{train,test}/*.csv (site/time/speed)
        /content/m4/<network>/gfs_{train,test}/*.csv (site/init_utc/fhr/u/v).
Never estimates any coefficient, quantile, threshold, or weight from test data.
"""
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from score_guard import check_cutoffs
HERE=Path('/content/m4'); LEADS=(10,20,30,60,120,180,240,300,360)
CFG=json.loads(Path('/content/config.json').read_text())

def read_obs(folder):
    ps=sorted(folder.glob('*.csv'))
    if not ps: raise ValueError(f'no observation files: {folder}')
    d=pd.concat((pd.read_csv(p) for p in ps),ignore_index=True)
    if 'station' in d: d=d.rename(columns={'station':'site'})
    if 'time_utc' in d: d=d.rename(columns={'time_utc':'valid_end_utc'})
    if not {'site','valid_end_utc','speed_ms'}<=set(d): raise ValueError('observation schema')
    d['valid_end_utc']=pd.to_datetime(d.valid_end_utc,utc=True)
    d['speed_ms']=pd.to_numeric(d.speed_ms,errors='coerce')
    d=d.dropna(subset=['speed_ms']).drop_duplicates(['site','valid_end_utc'])
    return d.set_index(['site','valid_end_utc']).speed_ms.sort_index()

def read_fc(folder):
    ps=sorted(folder.glob('*.csv'))
    if not ps: raise ValueError(f'no GFS files: {folder}')
    d=pd.concat((pd.read_csv(p) for p in ps),ignore_index=True)
    d['init_utc']=pd.to_datetime(d.init_utc,utc=True)
    d['valid_hour']=d.init_utc+pd.to_timedelta(d.fhr,unit='h')
    return d.set_index(['site','init_utc','valid_hour'])[['u','v']].sort_index()

def pick_init(issue,delay,source='GFS'):
    # User-visible issue time; GFS cycles 6h, AIWP cycles 12h.
    latest=issue-pd.Timedelta(hours=delay)
    return latest.floor('6h' if source=='GFS' else '12h')

def construct(obs,fc,sites,start,end,delay,source='GFS'):
    rows=[]
    step='h' if source=='GFS' else '6h'
    maximum=18 if source=='GFS' else 24
    issues=pd.date_range(start,end,freq='h',tz='UTC',inclusive='left')
    for site in sites:
        for issue in issues:
            p=obs.get((site,issue),np.nan)
            if not np.isfinite(p):continue
            init=pick_init(issue,delay,source)
            for lead in LEADS:
                valid=issue+pd.Timedelta(minutes=lead); mid=valid-pd.Timedelta(minutes=5)
                y=obs.get((site,valid),np.nan)
                if not np.isfinite(y): continue
                h0=mid.floor(step); h1=h0+pd.Timedelta(hours=1 if source=='GFS' else 6)
                if (h0-init).total_seconds()<0 or (h1-init).total_seconds()>maximum*3600:continue
                try:
                    v0=fc.loc[(site,init,h0)].to_numpy(float)
                    v1=fc.loc[(site,init,h1)].to_numpy(float)
                except KeyError:continue
                alpha=(mid-h0).total_seconds()/(3600 if source=='GFS' else 21600)
                raw=float(np.hypot(*(v0*(1-alpha)+v1*alpha)))
                age=(mid-init).total_seconds()/3600
                bucket=0 if age<=6 else 1 if age<=12 else 2
                rows.append((site,issue,init,valid,lead,float(y),float(p),raw,bucket))
    d=pd.DataFrame(rows,columns=['site','issue_utc','init_utc','valid_end_utc','lead_min','obs','P','R','bucket'])
    if d.empty:raise ValueError('no joint observed/forecast samples')
    # Every row is checked, not a sample. Last input is issue-time persistence.
    d['info_cutoff_utc']=d.issue_utc
    check_cutoffs(d.to_dict('records'),delay)
    return d

def train_model(d,full_obs):
    m={'corr':{},'O':{},'tau':None,'clim':{},'threshold':{},'residuals':{}}
    for (site,bucket),g in d.groupby(['site','bucket']):
        if len(g)<200:raise ValueError(f'insufficient MOS training: {site}:{bucket}, {len(g)}')
        b,a=np.polyfit(g.R,g.obs,1)
        m['corr'][f'{site}:{bucket}']=[float(a),float(b),int(len(g))]
    d=apply_corr(d,m)
    losses={}
    for tau in CFG['tau_minutes']:
        weight=np.exp(-d.lead_min.to_numpy()/tau)
        losses[tau]=float(np.mean(abs(d.obs-(weight*d.P+(1-weight)*d.F))))
    m['tau']=min(losses,key=losses.get)
    for lead,g in d.groupby('lead_min'):
        X=np.column_stack([np.ones(len(g)),g.P,g.F])
        c=np.linalg.lstsq(X,g.obs,rcond=None)[0]
        m['O'][str(lead)]=[float(x) for x in c]
    o=full_obs.rename('obs').reset_index()
    o['month']=o.valid_end_utc.dt.month;o['hour']=o.valid_end_utc.dt.hour
    for site,g in o.groupby('site'):
        m['threshold'][site]=float(np.quantile(g.obs,CFG['wind_threshold_quantile']))
    for key,g in o.groupby(['site','month','hour']):m['clim'][':'.join(map(str,key))]=float(g.obs.mean())
    # For 2024 Swiss Jan-Mar the corresponding Oct-Dec training months do not exist.
    # A separately declared fallback uses same-site same-UTC-hour mean, train only.
    for key,g in o.groupby(['site','hour']):m['clim'][f'{key[0]}:*:{key[1]}']=float(g.obs.mean())
    d=apply_model(d,m,clim=False)
    for typ in ('F','B'):
        for lead,g in d.groupby('lead_min'):
            r=(g.obs-g[typ]).to_numpy()
            m['residuals'][f'{typ}:net:{lead}']=np.quantile(r,[.05,.1,.9,.95]).tolist()
            for site,h in g.groupby('site'):
                m['residuals'][f'{typ}:{site}:{lead}']=np.quantile((h.obs-h[typ]).to_numpy(),[.05,.1,.9,.95]).tolist()
    return m

def apply_corr(d,m):
    d=d.copy()
    d['F']=[m['corr'][f'{s}:{b}'][0]+m['corr'][f'{s}:{b}'][1]*x for s,b,x in zip(d.site,d.bucket,d.R)]
    return d

def apply_model(d,m,clim=True):
    d=apply_corr(d,m)
    w=np.exp(-d.lead_min.to_numpy()/m['tau'])
    d['B']=w*d.P+(1-w)*d.F
    d['O']=[sum(c*x for c,x in zip(m['O'][str(l)],[1,p,f])) for l,p,f in zip(d.lead_min,d.P,d.F)]
    if clim:
        d['C']=[m['clim'].get(f'{s}:{t.month}:{t.hour}',m['clim'][f'{s}:*:{t.hour}']) for s,t in zip(d.site,d.valid_end_utc)]
    return d

def bootstrap(g,columns,seed,n=1000):
    # day blocks shared by all sites in one network; min reselected per draw
    rng=np.random.default_rng(seed)
    dates=g.issue_utc.dt.date.to_numpy()
    days=np.unique(dates)
    per_day=np.array([[np.abs(g.obs.to_numpy()[dates==day]-g[c].to_numpy()[dates==day]).sum() for c in columns]+[sum(dates==day)] for day in days])
    idx=rng.integers(0,len(days),size=(n,len(days)))
    sums=per_day[idx].sum(axis=1)
    vals=sums[:,:len(columns)]/sums[:,-1,None]
    return vals

def main_eval(d,m,net,delay,out,full_obs=None,weather=None,source='GFS'):
    d=apply_model(d,m)
    d['strong']=[y>=m['threshold'][s] for s,y in zip(d.site,d.obs)]
    if net=='OKC' and weather is None:
        raise ValueError('OKC weather classification required; do not label unclassified rows nonconvective')
    if full_obs is None:
        raise ValueError('Full 10-minute observations required to count contiguous events')
    if net=='OKC':
        weather=pd.read_csv(weather)
        weather['valid_end_utc']=pd.to_datetime(weather.valid_end_utc,utc=True)
        if weather.duplicated(['site','valid_end_utc']).any():raise ValueError('duplicate weather labels')
        weather=weather.set_index(['site','valid_end_utc']).convective
        if not weather.index.is_unique:raise ValueError('weather labels not unique')
        keys=pd.MultiIndex.from_frame(d[['site','valid_end_utc']])
        if not keys.isin(weather.index).all():raise ValueError('missing OKC weather labels')
        d['hazard']=np.where(weather.reindex(keys).to_numpy().astype(bool),'convective','nonconvective')
    else:d['hazard']='nonconvective_assumed'
    # Event IDs come from the complete 10-minute observed sequence, not just scored issue hours.
    event_lookup={};event_id=0
    for site in sorted(d.site.unique()):
        series=full_obs.xs(site,level=0).sort_index()
        high=series[series>=m['threshold'][site]]
        previous=None
        for t in high.index:
            if previous is None or t-previous>pd.Timedelta(minutes=30):event_id+=1
            event_lookup[(site,t)]=event_id;previous=t
    d['event_id']=[event_lookup.get((s,t),-1) for s,t in zip(d.site,d.valid_end_utc)]
    for typ in ('F','B'):
        for label in ('net','site'):
            bounds=[m['residuals'][f'{typ}:{label if label=="net" else s}:{l}'] for s,l in zip(d.site,d.lead_min)]
            a=np.asarray(bounds)
            for index,q in enumerate(('q05','q10','q90','q95')):d[f'{typ}_{label}_{q}']=d[typ]+a[:,index]
    d['network']=net;d['delay_h']=delay
    rows=[]
    for lead,g in d.groupby('lead_min'):
        names=['P','F','B','O','C','R']
        b=bootstrap(g,names,CFG['bootstrap_seed']+lead+delay*10000,CFG['bootstrap_days'])
        point={k:float(np.abs(g.obs-g[k]).mean()) for k in names}
        ratio=(point['B']-min(point['P'],point['F']))/min(point['P'],point['F'])
        dr=(b[:,2]-np.minimum(b[:,0],b[:,1]))/np.minimum(b[:,0],b[:,1])
        for i,k in enumerate(names):
            rows.append(dict(network=net,delay_h=delay,lead_min=int(lead),method=k,n=len(g),mae=point[k],lo=float(np.quantile(b[:,i],.025)),hi=float(np.quantile(b[:,i],.975)),D=ratio if k=='B' else None,D_lo=float(np.quantile(dr,.025)) if k=='B' else None,D_hi=float(np.quantile(dr,.975)) if k=='B' else None))
    pd.DataFrame(rows).to_csv(out/f'{net}_{source}_delay{delay}_mae.csv',index=False)
    secondary=[]
    for lead,g in d.groupby('lead_min'):
        for method in ('P','F','B'):
            labels=g.strong.astype(int).to_numpy()
            auc=float(roc_auc_score(labels,g[method])) if len(set(labels))==2 else None
            for fraction in CFG['top_k']:
                rank=g[method].to_numpy().argsort()[::-1]
                k=max(1,int(math.ceil(len(g)*fraction)))
                alarm=np.zeros(len(g),dtype=bool);alarm[rank[:k]]=True
                hit=float((alarm & labels.astype(bool)).sum()/labels.sum()) if labels.sum() else None
                event_rows=g.loc[g.strong,['event_id']].copy()
                event_rows['alarm']=alarm[g.strong.to_numpy()]
                if (event_rows.event_id<0).any():raise ValueError('unmapped strong-wind event')
                events=event_rows.groupby('event_id').alarm
                event_hit=float(events.any().mean()) if len(event_rows) else None
                # Expected event capture under uniform random row ranking on eligible scored rows.
                # Exact hypergeometric miss probability for each event size.
                from scipy.stats import hypergeom
                sizes=events.size().to_numpy();N=len(g)
                event_expect=float(np.mean(hypergeom.sf(0,N,sizes,k))) if len(sizes) else None
                secondary.append(dict(network=net,delay_h=delay,lead_min=int(lead),method=method,metric='auc_topk',k_fraction=fraction,auc=auc,topk_rows=hit,topk_events=event_hit,random_expectation_rows=k/N,random_expectation_events=event_expect,events=len(sizes),strong_rows=int(labels.sum())))
        for method in ('F','B'):
            for grouping in ('net','site'):
                for kind,h in [('all',g)]+[(label,g[g.hazard==label]) for label in ('convective','nonconvective','nonconvective_assumed') if (g.hazard==label).any()]:
                    for level,lower,upper in [(90,'q05','q95'),(80,'q10','q90')]:
                        hit=((h.obs>=h[f'{method}_{grouping}_{lower}'])&(h.obs<=h[f'{method}_{grouping}_{upper}'])).mean()
                        secondary.append(dict(network=net,delay_h=delay,lead_min=int(lead),method=method,metric='coverage',grouping=grouping,hazard=kind,nominal=level,coverage=float(hit),n=len(h),events=int(h.loc[h.strong,'event_id'].nunique())))
    pd.DataFrame(secondary).to_csv(out/f'{net}_{source}_delay{delay}_secondary.csv',index=False)
    turning={'network':net,'delay_h':delay,'F_le_P':None,'O_c1_lt_c2':None}
    summary=pd.DataFrame(rows)
    for lead in LEADS:
        sub=summary[summary.lead_min==lead].set_index('method')
        if len(sub)<6:continue
        if turning['F_le_P'] is None and sub.loc['F','mae']<=sub.loc['P','mae']:turning['F_le_P']=lead
        c=m['O'][str(lead)]
        if turning['O_c1_lt_c2'] is None and c[1]<c[2]:turning['O_c1_lt_c2']=lead
    (out/f'{net}_{source}_delay{delay}_turning.json').write_text(json.dumps(turning))
    return d

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--network',choices=['OKC','Swiss'],required=True);ap.add_argument('--mode',choices=['train','test'],required=True);ap.add_argument('--delay',type=int,default=4);ap.add_argument('--source',choices=['GFS','AIWP'],default='GFS')
    a=ap.parse_args();net=a.network;root=HERE/net;out=HERE/'output';out.mkdir(exist_ok=True)
    period={'OKC':{'train':('2022-01-01','2023-01-01'),'test':('2023-01-01','2024-01-01')},'Swiss':{'train':('2023-10-01','2024-01-01'),'test':('2024-01-01','2024-04-01')}}
    obs=read_obs(root/f'obs_{a.mode}');fc=read_fc(root/f'{a.source.lower()}_{a.mode}')
    d=construct(obs,fc,CFG['sites'][net],*period[net][a.mode],a.delay,a.source)
    mp=root/f'model_{a.source.lower()}_delay{a.delay}.json'
    if a.mode=='train':
        m=train_model(d,obs);mp.write_text(json.dumps(m));print('FIT',net,a.source,a.delay,len(d),'tau',m['tau'])
        (HERE/'pairs').mkdir(exist_ok=True)
        d.to_parquet(HERE/'pairs'/f'{net}_{a.source}_train_delay{a.delay}.parquet',index=False)
    else:
        if not mp.exists():raise FileNotFoundError(mp)
        m=json.loads(mp.read_text())
        weather=root/'weather_test.csv' if net=='OKC' else None
        e=main_eval(d,m,net,a.delay,out,obs,weather,a.source)
        (HERE/'pairs').mkdir(exist_ok=True)
        e.to_parquet(HERE/'pairs'/f'{net}_{a.source}_test_delay{a.delay}.parquet',index=False)
        print('SCORE',net,a.source,a.delay,len(e),'output',out)
