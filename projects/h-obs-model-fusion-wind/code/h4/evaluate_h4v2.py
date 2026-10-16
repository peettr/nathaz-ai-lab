import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import json,math
from pathlib import Path
import numpy as np,pandas as pd
from scipy.linalg import solve
from scipy.optimize import minimize_scalar
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent;dates=json.loads((R/'events_h4.json').read_text())['chosen_utc_dates'];land=set(pd.read_csv(R/'station_clean_h4.csv').query("status=='land'").station)
methods=['idw','ok75','okfit','era','era_resok75','era_resokfit'];gust_methods=['gust_idw','gust_ok75','gust_okfit']
def score(y,p):
    e=np.asarray(p,dtype=float)-np.asarray(y,dtype=float);e=e[np.isfinite(e)]
    return {'n':int(len(e)),'rmse':float(np.sqrt(np.mean(e*e))) if len(e) else None,'bias':float(np.mean(e)) if len(e) else None,'mae':float(np.mean(abs(e))) if len(e) else None}
def distance(s):
    la=np.deg2rad(s.lat.to_numpy());lo=np.deg2rad(s.lon.to_numpy());z=np.sin((la[:,None]-la[None,:])/2)**2+np.cos(la[:,None])*np.cos(la[None,:])*np.sin((lo[:,None]-lo[None,:])/2)**2
    return 12742*np.arcsin(np.minimum(1,np.sqrt(np.maximum(z,0))))
def fit(d,v):
    if len(v)<5:return 75.
    ii,jj=np.triu_indices(len(v),1);h=d[ii,jj];sv=.5*(v[ii]-v[jj])**2;bins=[]
    for low in np.arange(0,300,25):
        use=(h>=low)&(h<low+25)
        if use.sum()>=4:bins.append((float(h[use].mean()),float(sv[use].mean()),float(use.sum())**.5))
    if len(bins)<3:return 75.
    c,g,w=np.array(bins).T;sill=max(float(np.var(v)),.01)
    res=minimize_scalar(lambda r:np.mean((w*(g-sill*(1.08-np.exp(-c/r))))**2),bounds=(20,300),method='bounded',options={'xatol':2})
    return float(res.x)
def weight(d,ix,i,r):
    n=len(ix);k=np.empty((n+1,n+1));k[:n,:n]=np.exp(-d[np.ix_(ix,ix)]/r)+np.eye(n)*.08;k[:n,n]=1;k[n,:n]=1;k[n,n]=0
    try:return solve(k,np.r_[np.exp(-d[ix,i]/r),1.],assume_a='sym')[:n]
    except Exception:return np.full(n,1/n)
allp=[];status={}
for day in dates:
    tag=day.replace('-','');grid=pd.read_csv(R/f'grid_{tag}_h4.csv.gz',parse_dates=['valid']);grid=grid[grid.station.isin(land)].copy()
    stations=grid.drop_duplicates('station').sort_values('station').reset_index(drop=True);names=stations.station.tolist();n=len(names);d=distance(stations);base=grid.set_index(['valid','station']).sort_index();times=sorted(grid.valid.unique());obs=base.obs.unstack('station').reindex(index=times,columns=names);gust=base.gust.unstack('station').reindex(index=times,columns=names);era=base.era.unstack('station').reindex(index=times,columns=names)
    eligible={s:bool(obs[s].count()>=math.ceil(.75*361) and gust[s].count()>=math.ceil(.75*361)) for s in names}
    status[day]={'land_candidate':n,'eligible_both':int(sum(eligible.values())),'minutes':361,'excluded':{s:{'wind_minutes':int(obs[s].count()),'gust_minutes':int(gust[s].count())} for s in names if not eligible[s]}}
    # Fit by UTC hour from median training wind within hour, leave target station out.
    ranges={}
    for h,ii in pd.Series(range(len(times)),index=times).groupby(pd.DatetimeIndex(times).floor('h')):
        mid=obs.iloc[ii.values].median().to_numpy();e=era.iloc[ii.values].median().to_numpy();gm=gust.iloc[ii.values].median().to_numpy()
        for i in range(n):
            ix=np.flatnonzero(np.isfinite(mid)&(np.arange(n)!=i));ig=np.flatnonzero(np.isfinite(gm)&(np.arange(n)!=i))
            ranges[(h,i)]=(fit(d[np.ix_(ix,ix)],mid[ix]) if len(ix)>=5 else 75.,fit(d[np.ix_(ix,ix)],(mid-e)[ix]) if len(ix)>=5 else 75.,fit(d[np.ix_(ig,ig)],gm[ig]) if len(ig)>=5 else 75.)
    rows=[]
    for t in times:
        y=obs.loc[t].to_numpy();g=gust.loc[t].to_numpy();b=era.loc[t].to_numpy();hour=pd.Timestamp(t).floor('h')
        for i,s in enumerate(names):
            if not eligible[s]:continue
            ix=np.flatnonzero(np.isfinite(y)&(np.arange(n)!=i));ig=np.flatnonzero(np.isfinite(g)&(np.arange(n)!=i));row={'event':day,'station':s,'valid':t,'obs':y[i],'gust':g[i],'distance_km':float(d[ix,i].min()) if len(ix) else np.nan}
            if len(ix)>=4 and np.isfinite(y[i]):
                w=1/np.maximum(d[ix,i],.01)**2;w/=w.sum();rf,rr,_=ranges[(hour,i)];w75=weight(d,ix,i,75.);wf=weight(d,ix,i,rf);wr=weight(d,ix,i,rr)
                row.update(idw=w@y[ix],ok75=w75@y[ix],okfit=wf@y[ix],era=b[i],era_resok75=b[i]+w75@(y-b)[ix],era_resokfit=b[i]+wr@(y-b)[ix])
            if len(ig)>=4 and np.isfinite(g[i]):
                w=1/np.maximum(d[ig,i],.01)**2;w/=w.sum();_,_,rg=ranges[(hour,i)]
                row.update(gust_idw=w@g[ig],gust_ok75=weight(d,ig,i,75.)@g[ig],gust_okfit=weight(d,ig,i,rg)@g[ig])
            rows.append(row)
    p=pd.DataFrame(rows);allp.append(p);status[day]['predicted_wind_stations']=int(p[p.ok75.notna()].station.nunique());status[day]['predicted_gust_stations']=int(p[p.gust_ok75.notna()].station.nunique());print(day,status[day],flush=True)
p=pd.concat(allp,ignore_index=True);p.to_csv(R/'predictions_h4v2.csv.gz',index=False,compression='gzip')
peaks=[]
for (ev,st),x in p.groupby(['event','station']):
    # paired minute mask shared by continuous-wind methods
    x=x[x[methods].notna().all(axis=1)]
    if len(x)<4:continue
    row={'event':ev,'station':st,'obs':x.obs.max(),'distance_km':x.distance_km.iloc[0],'minutes_scored':len(x)}
    for m in methods:row[m]=x[m].max()
    gx=x[x[gust_methods].notna().all(axis=1)&x.gust.notna()];row['gust']=gx.gust.max() if len(gx)>0 else np.nan
    for m in gust_methods:row[m]=gx[m].max() if len(gx)>0 else np.nan
    peaks.append(row)
q=pd.DataFrame(peaks);q.to_csv(R/'peaks_h4v2.csv',index=False)
def summary(z,h):
    if len(z)<8:return {'n':len(z),'evaluable':False}
    by={m:{'peak':score(z.obs,z[m]),'minute':score(h.obs,h[m])} for m in methods}
    baseline=min(['idw','ok75','okfit'],key=lambda m:by[m]['peak']['rmse']);fusion=min(['era_resok75','era_resokfit'],key=lambda m:by[m]['peak']['rmse']);gain=1-by[fusion]['peak']['rmse']/by[baseline]['peak']['rmse'];wins=int(((z[fusion]-z.obs).abs()<(z[baseline]-z.obs).abs()).sum());n=len(z)
    verdict='值得' if gain>=.2 and wins/n>=2/3 else ('有条件' if gain>=.1 or wins/n>=2/3 else '插值够用')
    isolated=int(sum((row.obs-z.loc[(z.station!=row.station)&(z.event==row.event),'obs'].max())>=5 for row in z.itertuples()))
    distances=[]
    for label,sel in [('<25',z.distance_km<25),('25-50',(z.distance_km>=25)&(z.distance_km<50)),('>=50',z.distance_km>=50)]:
        zz=z[sel];distances.append({'bin':label,'n':len(zz),'baseline':score(zz.obs,zz[baseline]),'fusion':score(zz.obs,zz[fusion])})
    return {'n':n,'evaluable':True,'methods':by,'baseline':baseline,'best_fusion':fusion,'gain':gain,'wins':wins,'verdict':verdict,'isolated_peak_count':isolated,'distances':distances,'gust_peak':{m:score(z.gust,z[m]) for m in gust_methods}}
met={day:summary(q[q.event==day],p[p.event==day]) for day in dates};accepted=[d for d in dates if met[d]['evaluable']];met['COMBINED']=summary(q[q.event.isin(accepted)],p[p.event.isin(accepted)]) if accepted else {'n':0,'evaluable':False}
(R/'metrics_h4v2.json').write_text(json.dumps({'status':status,'metrics':met,'selected':dates,'evaluated':accepted,'units':'m/s','sources':['NOAA NCEI Storm Events','Iowa Environmental Mesonet ASOS1MIN','Google Research ARCO ERA5','ESA WorldCover'], 'caveat':'ERA5 assimilation of heldout stations not established; HRRR f01 not run; gust fusion not evaluable without gust background'},ensure_ascii=False,indent=2))
fig,ax=plt.subplots(figsize=(7,6))
for day in accepted:
    z=q[q.event==day];f=met[day]['best_fusion'];ax.scatter(z.obs,z[f],s=22,alpha=.7,label=day)
ax.plot([0,40],[0,40],'k--');ax.set(xlim=(0,40),ylim=(0,40),xlabel='Observed 1-min peak sustained wind (m/s)',ylabel='LOO ERA5 + residual OK peak (m/s)',title='IEM ASOS1MIN / NOAA Storm Events / ARCO ERA5');ax.legend();fig.tight_layout();fig.savefig(R/'peak_scatter_h4v2.png',dpi=160)
print({k:{z:v.get(z) for z in ['n','gain','wins','verdict','isolated_peak_count']} for k,v in met.items()})
