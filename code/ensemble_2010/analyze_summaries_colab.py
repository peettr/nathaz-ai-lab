"""Run only in Colab CPU after all ten independent member summaries are verified."""
import csv,json
from pathlib import Path
import numpy as np
from scipy.stats import genextreme,genpareto
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path('/content/ace_analysis');N=10;B=600
YEARS=np.arange(1980,2010)
MASKS={'holdout':(YEARS>=1996)&(YEARS<=2009),'training':(YEARS>=1980)&(YEARS<=1994)}
ref=json.loads((ROOT/'reference_summary.json').read_text())
members=[json.loads((ROOT/f'm{k:02d}_summary.json').read_text()) for k in range(1,11)]
order=ref['order'];assert len(order)==8
for k,m in enumerate(members,1):
    assert m['member']==k and m['years']==ref['years'] and m['order']==order
rmax=np.array(ref['maxima']);amax=np.array([m['maxima'] for m in members]);assert rmax.shape==(30,8) and amax.shape==(10,30,8)
thr=np.array(json.loads((ROOT/'threshold.json').read_text())['threshold'])
def gev(x):
    try:
        c,l,s=genextreme.fit(x)
        z=genextreme.ppf(.98,c,loc=l,scale=s)
        return float(z) if np.isfinite(z) and z>0 else np.nan
    except (ValueError,RuntimeError):return np.nan
def pot(excess,n_season,threshold):
    x=np.array([v for a in excess for v in a],dtype=float)
    if len(x)<20:return np.nan
    try:
        c,_,s=genpareto.fit(x,floc=0)
        z=threshold+genpareto.ppf(1+np.log(.98)/(len(x)/n_season),c,loc=0,scale=s)
        return float(z) if np.isfinite(z) and z>0 else np.nan
    except (ValueError,RuntimeError):return np.nan
def stat(values,peaks,n,threshold):
    return np.array([np.median(values),np.quantile(values,.9),gev(values),pot(peaks,n,threshold)])
rng=np.random.default_rng(20261015);rows=[]
for cohort,mask in MASKS.items():
    yy=np.flatnonzero(mask);count=len(yy)
    for j,site in enumerate(order):
        obs=stat(rmax[yy,j],[ref['pot_excess'][y][j] for y in yy],count,thr[j])
        sim=stat(amax[:,yy,j].ravel(),[members[m]['pot_excess'][y][j] for m in range(10) for y in yy],10*count,thr[j])
        samples=np.empty((B,4))
        for b in range(B):
            mi=rng.integers(0,10,size=10);yi=rng.choice(yy,size=count,replace=True)
            values=amax[np.ix_(mi,yi,[j])].ravel()
            peaks=[members[m]['pot_excess'][y][j] for m in mi for y in yi]
            samples[b]=stat(values,peaks,10*count,thr[j])
        lo=np.nanquantile(samples,.05,axis=0);hi=np.nanquantile(samples,.95,axis=0)
        row={'cohort':cohort,'site':site,'n_years':count,'n_members':10,'reference_threshold_mps':thr[j]}
        for i,name in enumerate(['median','p90','gev50','pot50']):
            row[f'era_{name}']=obs[i];row[f'ace_{name}']=sim[i];row[f'ace_{name}_lo90']=lo[i];row[f'ace_{name}_hi90']=hi[i]
            row[f'{name}_era_inside90']=bool(np.isfinite(obs[i]) and lo[i]<=obs[i]<=hi[i])
            row[f'{name}_bias_pct']=100*(sim[i]/obs[i]-1) if np.isfinite(sim[i]) and np.isfinite(obs[i]) else np.nan
            row[f'{name}_valid_bootstrap']=int(np.isfinite(samples[:,i]).sum())
        rows.append(row);print('SCORED',cohort,site,'GEV50',row['gev50_bias_pct'],flush=True)
with (ROOT/'formal_metrics.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
(ROOT/'formal_metrics.json').write_text(json.dumps({'methods':'10 independent 1979 monthly initial conditions; aligned forcing-year block + member bootstrap, B=600; fixed ERA5 training-p95 POT threshold, 72h decluster within season','source':'ACE2-ERA5 HF f25123c52d7faa8f3533816a311cf3353ee83daa; WeatherBench2 ERA5 0.25degree U/V conservative to ACE grid','seed':20261015,'rows':rows},indent=2))
for cohort in MASKS:
    subset=[r for r in rows if r['cohort']==cohort]
    fig,axs=plt.subplots(2,2,figsize=(14,9))
    for ax,key,title in zip(axs.flat,['median','p90','gev50','pot50'],['Season max median','Season max p90','Season GEV 50-year','POT 50-year']):
        x=np.arange(8);obs=np.array([r['era_'+key] for r in subset]);sim=np.array([r['ace_'+key] for r in subset]);lo=np.array([r['ace_'+key+'_lo90'] for r in subset]);hi=np.array([r['ace_'+key+'_hi90'] for r in subset])
        ax.errorbar(x+.12,sim,yerr=np.array([sim-lo,hi-sim]),fmt='s',capsize=3,label='ACE2 90% ensemble bootstrap')
        ax.plot(x-.12,obs,'ko',label='ERA5 reference');ax.set_xticks(x,order,rotation=25);ax.set_ylabel('m/s');ax.set_title(title);ax.grid(alpha=.2)
    axs[0,0].legend(fontsize=8)
    fig.suptitle(f'ACE2–ERA5 {cohort}: {subset[0]["n_years"]} complete Oct–Mar seasons; 10 monthly ICs')
    fig.text(.02,.01,'Source: Ai2 ACE2-ERA5 HF; ECMWF ERA5 via WeatherBench2 0.25° conservatively remapped. Cold-season proxy, not event-classified.',fontsize=8)
    fig.tight_layout(rect=[0,.035,1,.95]);fig.savefig(ROOT/f'{cohort}_comparison.png',dpi=130);plt.close(fig)
print('FORMAL_ANALYSIS_DONE',len(rows),flush=True)
