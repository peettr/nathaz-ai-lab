"""ACE2 single-member rank and ERA5 peak timestamps; run on Colab CPU only."""
import csv, json
from pathlib import Path
import numpy as np
from scipy.stats import genextreme, genpareto
R=Path('/content/member_rank_events')
ref=json.loads((R/'reference_summary.json').read_text())
mem=[json.loads((R/f'm{k:02d}_summary.json').read_text()) for k in range(1,11)]
threshold=json.loads((R/'threshold.json').read_text())['threshold']
order=ref['order']; years=np.array(ref['years']); assert years.tolist()==list(range(1980,2010))
assert len(mem)==10 and len(set(m['member'] for m in mem))==10
assert all(m['member']==k and m['order']==order and m['years']==ref['years'] for k,m in enumerate(mem,1))
def gev(x):
    c,l,s=genextreme.fit(x)
    return float(genextreme.ppf(.98,c,loc=l,scale=s))
def pot(excess,n,t):
    x=np.array([v for season in excess for v in season],float)
    if len(x)<20:return float('nan')
    c,_,s=genpareto.fit(x,floc=0)
    return float(t+genpareto.ppf(1+np.log(.98)/(len(x)/n),c,loc=0,scale=s))
def stats(d,ids,j):
    vals=np.array(d['maxima'])[ids,j]
    return [gev(vals),pot([d['pot_excess'][i][j] for i in ids],len(ids),threshold[j]),float(np.quantile(vals,.9))]
rows=[]
for cohort,ids in [('holdout',np.flatnonzero((years>=1996)&(years<=2009))),('training',np.flatnonzero((years>=1980)&(years<=1994)))]:
    assert len(ids)==(14 if cohort=='holdout' else 15)
    for j,site in enumerate(order):
        r=stats(ref,ids,j); a=np.array([stats(d,ids,j) for d in mem]);
        for h,metric in enumerate(['gev50','pot50','p90']):
            v=a[:,h]; nbelow=int(np.sum(v<r[h])); nabove=int(np.sum(v>r[h])); ties=int(np.sum(v==r[h]));
            rows.append({'cohort':cohort,'site':site,'n_seasons':len(ids),'metric':metric,'era_mps':r[h],
                **{f'm{k:02d}_mps':v[k-1] for k in range(1,11)},'min_mps':np.min(v),'median_mps':np.median(v),'max_mps':np.max(v),
                'n_member_below_era':nbelow,'n_member_above_era':nabove,'ties':ties,
                'era_rank_among_11':nbelow+1 if ties==0 else '',
                'outside_member_range':bool(r[h]<np.min(v) or r[h]>np.max(v))})
        print('RANK',cohort,site,'GEV50',r[0],a[:,0].min(),a[:,0].max(),flush=True)
with (R/'member_ranks.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,rows[0]);w.writeheader();w.writerows(rows)
peaks=[]
for year in range(1996,2010):
    with np.load(R/'reference'/f'cold_{year}.npz') as z:
        t=z['time']; s=np.hypot(z['u'],z['v']);
        expected=np.arange(np.datetime64(f'{year}-10-01T00'),np.datetime64(f'{year+1}-04-01T00'),np.timedelta64(6,'h'))
        assert np.array_equal(t,expected) and s.shape==(len(t),8)
        for site in ['KDSM','KOMA']:
            j=order.index(site);idx=int(np.argmax(s[:,j]));
            assert np.isclose(s[idx,j],ref['maxima'][year-1980][j],atol=1e-5)
            peaks.append({'site':site,'season_start':year,'time_utc':str(t[idx]),'speed_mps':float(s[idx,j]),
                'other_plain_site_mps':float(s[idx,order.index('KOMA' if site=='KDSM' else 'KDSM')])})
peaks.sort(key=lambda x:(x['site'],-x['speed_mps']))
with (R/'era_season_peaks.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,peaks[0]);w.writeheader();w.writerows(peaks)
print('TOP5',json.dumps({site:[p for p in peaks if p['site']==site][:5] for site in ['KDSM','KOMA']}),flush=True)
print('DONE',len(rows),len(peaks),flush=True)
