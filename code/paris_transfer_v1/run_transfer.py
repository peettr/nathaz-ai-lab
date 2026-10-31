"""A1 Paris cross-site MOS transfer; reuse v2 station forecasts, no new gridded fetch.
Run: .venv/bin/python run_transfer.py. METAR CSV is the single IEM query documented in provenance.md.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent
V2=R.parent/'paris_lidar_v2'/'paired_station.csv.gz'
KEY=['init_utc','valid_utc','lead_h']
MONTHS=['2023-09','2023-10','2023-11','2023-12','2024-01','2024-02']
KNOT=0.5144444444444445

def linear(x,y):
    x=np.asarray(x);y=np.asarray(y);m=np.isfinite(x)&np.isfinite(y)
    if m.sum()<20: raise ValueError('under 20 training pairs')
    b,a=np.polyfit(x[m],y[m],1)
    return float(a),float(b)

def raw(d,src):
    return np.hypot(d.fc_u100,d.fc_v100) if src=='GFS' else np.hypot(d.fc_u,d.fc_v)*np.log(111/.03)/np.log(10/.03)

def prob(train_x,train_y,test_x,threshold=8):
    x=np.asarray(train_x); y=(np.asarray(train_y)>=threshold).astype(int)
    if np.unique(y).size<2: return np.full(len(test_x),y.mean(),float)
    model=LogisticRegression(C=1000,max_iter=300).fit(x.reshape(-1,1),y)
    return model.predict_proba(np.asarray(test_x).reshape(-1,1))[:,1]

def ci_diff(g,col,n=3000):
    g=g.copy();g['day']=g.valid_utc.dt.floor('D')
    a=g.groupby('day').apply(lambda q:pd.Series({'s':np.abs(q[col]-q.wind).sum(),'b':np.abs(q.S0-q.wind).sum(),'n':len(q)}),include_groups=False)
    rng=np.random.default_rng(20261014+len(col)+int(g.lead_h.iloc[0]));ind=rng.integers(0,len(a),size=(n,len(a)))
    sample=a.to_numpy()[ind].sum(axis=1)
    rel=(sample[:,0]/sample[:,2])/(sample[:,1]/sample[:,2])-1
    absolute=(sample[:,0]-sample[:,1])/sample[:,2]
    return {'relative_pct':float(100*(a.s.sum()/a.b.sum()-1)),'relative_pct_ci95':(100*np.quantile(rel,[.025,.975])).tolist(), 'mae_difference':float((a.s.sum()-a.b.sum())/a.n.sum()),'mae_difference_ci95':np.quantile(absolute,[.025,.975]).tolist(),'days':len(a)}

def main():
    d=pd.read_csv(V2,parse_dates=['init_utc','valid_utc'])
    m=pd.read_csv(R/'airport_metar_202309_202402.csv',parse_dates=['valid'])
    m=m[m.station=='LFPO'].copy();m['valid_utc']=m.valid.dt.tz_localize('UTC');m['airport10']=m.sknt*KNOT
    # Most recent routine/special report within 30 minutes before verification hour; no future observation.
    m=m.sort_values('valid_utc').drop_duplicates('valid_utc',keep='last')
    output=[];details=[];diagnostics={}
    for src in ['GFS','GRAP_v100_GFS']:
        method='direct100' if src=='GFS' else 'log_z0_0p03'
        base=d[(d.station=='PALUPD')&(d.target_agl==100)&(d.source==src)&(d.method==method)].copy()
        base['raw']=raw(base,src)
        # v2 S0 original out-of-fold predictions retained; do not refit from held-out observations.
        base=base.sort_values('valid_utc')
        base=pd.merge_asof(base,m[['valid_utc','airport10']].sort_values('valid_utc'),on='valid_utc',direction='backward',tolerance=pd.Timedelta('30min'))
        base['month']=base.valid_utc.dt.strftime('%Y-%m')
        base['S0']=base.pred; base['S3']=base.raw
        for lead in [24,48]:
            g=base[base.lead_h==lead].copy()
            if g.duplicated(KEY).any():raise ValueError('non-unique city forecast')
            # For each fold, train ground-only MOS on airport observations vs the archived PALUPD grid 10m forecast.
            # This is a city-grid-to-airport proxy, not collocated airport-grid MOS.
            for hold in MONTHS:
                tr=g[g.month!=hold];te=g[g.month==hold].copy()
                if te.empty:continue
                xtr=np.hypot(tr.fc_u,tr.fc_v); xte=np.hypot(te.fc_u,te.fc_v)
                airport=tr[tr.airport10.notna()]; a,b=linear(np.hypot(airport.fc_u,airport.fc_v),airport.airport10)
                ground=np.maximum(0,a+b*xte)
                # no PALUPD high-altitude information; neutral-profile assumed z0
                f=np.log(111/.03)/np.log(10/.03)
                te['S1']=ground*f
                te['p1']=prob(np.maximum(0,a+b*np.hypot(airport.fc_u,airport.fc_v)),airport.airport10,ground,8/f)
                te['p3']=te.S3 # monotonic discriminant, no local probability calibration
                te['p0']=te.prob8
                for site in ['PAARBO','PACHEM']:
                    sub=d[(d.station==site)&(d.target_agl==100)&(d.source==src)&(d.method==method)&(d.lead_h==lead)].copy()
                    sub['month']=pd.to_datetime(sub.valid_utc).dt.strftime('%Y-%m')
                    sub=sub[sub.month!=hold]
                    xx=raw(sub,src);aa,bb=linear(xx,sub.wind)
                    v=np.maximum(0,aa+bb*te.raw)
                    te['S2_'+site]=v
                    te['p2_'+site]=prob(np.maximum(0,aa+bb*xx),sub.wind,v)
                    diagnostics[f'{src}_{lead}_{hold}_{site}']={'n_train':len(sub),'a':aa,'b':bb}
                details.append(te)
        diagnostics[f'{src}_airport_available']={'all':len(base),'nonmissing':int(base.airport10.notna().sum())}
    allp=pd.concat(details,ignore_index=True)
    cols=['S0','S1','S2_PAARBO','S2_PACHEM','S3']
    for (src,lead),gg in allp.groupby(['source','lead_h']):
        # identical validation timestamps across scenarios and sources. METAR missing removes the timestamp for all.
        g=gg.dropna(subset=['airport10']+cols).copy()
        for name in cols:
            val=g[name];err=val-g.wind;y=(g.wind>=8).astype(int)
            pc={'S0':'p0','S1':'p1','S2_PAARBO':'p2_PAARBO','S2_PACHEM':'p2_PACHEM','S3':'p3'}[name]
            p=g[pc]
            hit=int(((val>=8)&(y==1)).sum());miss=int(((val<8)&(y==1)).sum());false=int(((val>=8)&(y==0)).sum())
            rec={'source':src,'lead_h':int(lead),'scheme':name,'n':len(g),'events8':int(y.sum()),'mae':float(np.abs(err).mean()),'bias':float(err.mean()),'auc8':float(roc_auc_score(y,p)),'csi8':float(hit/(hit+miss+false)) if hit+miss+false else None,'hits':hit,'misses':miss,'false_alarms':false}
            if name!='S0':rec['vs_S0']=ci_diff(g,name)
            output.append(rec)
    # Strict same sample between GFS and GraphCast too.
    keys=allp.groupby(['init_utc','valid_utc','lead_h']).source.nunique();assert keys.min()==2
    allp[['station','source','init_utc','valid_utc','lead_h','month','wind','airport10']+cols+['p0','p1','p2_PAARBO','p2_PACHEM','p3']].to_csv(R/'paired_transfer.csv.gz',index=False,compression='gzip')
    sensitivity={}
    for (src,lead),g in allp.groupby(['source','lead_h']):
        # S1's ground MOS output is recovered before applying the default neutral-profile factor.
        ground=g.S1/(np.log(111/.03)/np.log(10/.03))
        factors={'log_z0_0p03':np.log(111/.03)/np.log(10/.03),'log_z0_0p3':np.log(111/.3)/np.log(10/.3),
                 'power_alpha_0p14':(111/10)**.14,'power_alpha_0p2':(111/10)**.2,'power_alpha_0p3':(111/10)**.3}
        sensitivity[f'{src}_{lead}']={k:float(np.mean(np.abs(ground*f-g.wind))) for k,f in factors.items()}
    payload={'records':output,'s1_profile_sensitivity_mae':sensitivity,'fold_transfer_coefficients':diagnostics,'definitions':{'S1':'LFPO METAR 10 m MOS against PALUPD-grid 10 m; neutral log z0=0.03m', 'S2':'suburban lidar MOS transfer, 100m gates PAARBO 102m / PACHEM 104m','S3':'raw mode 100m GFS or GraphCast 10m log-law','S0':'v2 local MOS out-of-fold prediction'}}
    (R/'metrics.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False))
    fig,axs=plt.subplots(1,2,figsize=(12,4.4))
    for ax,src in zip(axs,['GFS','GRAP_v100_GFS']):
        for lead,mark in [(24,'o'),(48,'s')]:
            z=[next(x for x in output if x['source']==src and x['lead_h']==lead and x['scheme']==c)['mae'] for c in cols]
            ax.plot(cols,z,marker=mark,label=f'{lead} h')
        ax.set(title=src,ylabel='111 m MAE (m/s)',xlabel='No-local calibration schemes');ax.legend();ax.grid(alpha=.3);ax.tick_params(axis='x',rotation=25)
    fig.text(.01,.01,'Morrison et al. 2025 Zenodo 17710093; NOAA/NCEP GFS; NOAA/CIRA AIWP; IEM Paris METAR (LFPO)',fontsize=8)
    fig.tight_layout(rect=(0,.04,1,1));fig.savefig(R/'transfer_mae.png',dpi=160);plt.close(fig)
    print(json.dumps(output,ensure_ascii=False))
if __name__=='__main__':main()
