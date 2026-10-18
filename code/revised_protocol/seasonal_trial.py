"""Reanalyse existing paired 1979–2008 ACE2-ERA5 and WB2 ERA5 point series.
Cold-season proxy only; no convection/TC event classification. New outputs only.
"""
from pathlib import Path
import csv
import numpy as np
from scipy.stats import genextreme, genpareto

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent
SITES=['KMSP','KDSM','KOMA','KDTW','KPIT','KALB','DFW','AUS']
YEARS=list(range(1979,2008)) # 1979/80..2007/08 complete Oct-Mar seasons
# POT threshold is empirical 95th percentile of paired ERA5 cold-season 6h values,
# fixed across ACE/ERA. A run of samples > threshold is one event, separated by
# at least 72 hours (12 six-hour slots). This is a stipulated sensitivity, not literature-calibrated.
GAP=12

def peaks(v, threshold):
    hit=np.flatnonzero(v>threshold)
    if len(hit)==0:return np.empty(0)
    breaks=np.flatnonzero(np.diff(hit)>GAP)+1
    return np.array([v[g].max() for g in np.split(hit,breaks)])

def gev50(mx):
    shape,loc,scale=genextreme.fit(mx)
    return float(genextreme.ppf(.98,shape,loc=loc,scale=scale)),float(shape)

def pot50(v,season,threshold):
    allpeaks=np.concatenate([peaks(v[season==y],threshold) for y in YEARS])
    if len(allpeaks)<20: return np.nan,np.nan,len(allpeaks)
    shape,_,scale=genpareto.fit(allpeaks-threshold,floc=0)
    rate=len(allpeaks)/len(YEARS)
    q=1-1/(50*rate)
    return float(threshold+genpareto.ppf(q,shape,loc=0,scale=scale)),float(shape),len(allpeaks)

rows=[]
for site in SITES:
    with np.load(ROOT/f'points_{site}.npz') as d:
        t=d['time']; ace=d['ace'].astype(float); era=d['era'].astype(float)
    assert len(t)==len(ace)==len(era)==43831
    # assign January-March to preceding year's October; exclude April-September
    month=t.astype('datetime64[M]').astype(int)%12+1
    year=t.astype('datetime64[Y]').astype(int)+1970
    season=np.where(month<=3,year-1,year)
    valid=((month>=10)|(month<=3)) & np.isin(season,YEARS)
    a,e,s=ace[valid],era[valid],season[valid]
    assert len(np.unique(s))==29 and all(np.sum(s==y)>700 for y in YEARS)
    threshold=float(np.quantile(e,.95))
    ma=np.array([a[s==y].max() for y in YEARS]);me=np.array([e[s==y].max() for y in YEARS])
    av,ash=gev50(ma); ev,esh=gev50(me)
    ap,aps,an=pot50(a,s,threshold);ep,eps,en=pot50(e,s,threshold)
    row={'site':site,'n_complete_seasons':len(YEARS),'n_paired_6h':len(a),
         'threshold_era5_p95_ms':threshold,'ace_mean_ms':a.mean(),'era_mean_ms':e.mean(),
         'ace_median_ms':np.median(ma),'era_median_ms':np.median(me),
         'ace_p90_ms':np.quantile(ma,.9),'era_p90_ms':np.quantile(me,.9),
         'ace_gev_50yr_ms':av,'era_gev_50yr_ms':ev,'ace_gev_shape_scipy':ash,'era_gev_shape_scipy':esh,
         'ace_pot_50yr_ms':ap,'era_pot_50yr_ms':ep,'ace_pot_shape_scipy':aps,'era_pot_shape_scipy':eps,
         'ace_pot_clusters':an,'era_pot_clusters':en}
    for key in ['mean','median','p90','gev_50yr','pot_50yr']:
        row[key+'_bias_pct']=100*(row['ace_'+key+'_ms']/row['era_'+key+'_ms']-1)
    rows.append(row)
with (OUT/'seasonal_trial.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
for r in rows:
    print(r['site'],r['n_paired_6h'],*[round(r[k+'_bias_pct'],2) for k in ['median','p90','gev_50yr','pot_50yr']],r['ace_pot_clusters'],r['era_pot_clusters'])
print('DONE',len(rows),'sites,',len(YEARS),'complete seasons; no ensemble CI')
