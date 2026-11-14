"""Frozen new-site single-member ranking and pressure anomaly auxiliary (Colab CPU)."""
import csv,json
from pathlib import Path
import numpy as np
from scipy.stats import genextreme,genpareto
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path('/content/cnew_analysis');R.mkdir(exist_ok=True)
ref=json.loads((R/'reference_summary.json').read_text());mem=[json.loads((R/f'm{k:02d}_summary.json').read_text()) for k in range(1,11)]
threshold=json.loads((R/'threshold.json').read_text())['threshold'];sites=json.loads((R/'sites_frozen.json').read_text());order=sites['order'];years=np.array(ref['years']);assert years.tolist()==list(range(1980,2010))
assert all(m['member']==k and m['order']==order and m['years']==ref['years'] for k,m in enumerate(mem,1))
valid=[k for k in order if k!='KMKE'];assert len(valid)==7

def stats(d,ids,j):
 v=np.asarray(d['maxima'])[ids,j];c,l,s=genextreme.fit(v);gev=float(genextreme.ppf(.98,c,loc=l,scale=s))
 peaks=np.array([v for y in ids for v in d['pot_excess'][y][j]],dtype=float)
 if len(peaks)>=20:
  c,_,s=genpareto.fit(peaks,floc=0);pot=float(threshold[j]+genpareto.ppf(1+np.log(.98)/(len(peaks)/len(ids)),c,loc=0,scale=s))
 else:pot=np.nan
 return (gev,pot,float(np.quantile(v,.9)))
rows=[];counts={}
for cohort,ids in [('holdout',np.flatnonzero((years>=1996)&(years<=2009))),('training',np.flatnonzero((years>=1980)&(years<=1994)))]:
 assert len(ids)==(14 if cohort=='holdout' else 15)
 for j,site in enumerate(order):
  if site not in valid:continue
  r=stats(ref,ids,j);a=np.array([stats(d,ids,j) for d in mem]);assert np.isfinite(a).all() and np.isfinite(r).all(),(cohort,site)
  for h,metric in enumerate(['gev50','pot50','p90']):
   v=a[:,h];rank=int((v<r[h]).sum())+1;assert not np.any(v==r[h])
   row={'cohort':cohort,'site':site,'cell_lat':sites['stations'][site]['cell_lat'],'cell_lon_east':sites['stations'][site]['cell_lon'],'n_seasons':len(ids),'metric':metric,'era_mps':r[h],**{f'm{k:02d}_mps':v[k-1] for k in range(1,11)},'member_median_mps':float(np.median(v)),'median_relative_bias_pct':float(100*(np.median(v)/r[h]-1)),'era_rank_among_11':rank}
   rows.append(row)
 for metric in ('gev50','pot50','p90'):
  rr=[v for v in rows if v['cohort']==cohort and v['metric']==metric]
  counts[cohort+'_'+metric]={'rank1':sum(v['era_rank_among_11']==1 for v in rr),'rank11':sum(v['era_rank_among_11']==11 for v in rr),'out_of_range':sum(v['era_rank_among_11'] in (1,11) for v in rr),'n_valid':len(rr),'n_preregistered':8}
with (R/'ranks.csv').open('x',newline='') as f:w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
gate=counts['holdout_gev50'];verdict=('通过' if gate['out_of_range']<=2 else '压尾' if gate['rank11']>=3 and gate['rank1']<3 else '偏高' if gate['rank1']>=3 and gate['rank11']<3 else '说不清')
# Auxiliary uses 30 complete cold seasons; per-member climatology already applied upstream.
pref=json.loads((R/'era_pressure_minima.json').read_text());pm=[json.loads((R/f'm{k:02d}_pressure_minima.json').read_text()) for k in range(1,11)]
assert [v['season'] for v in pref['rows']]==list(range(1980,2010))
assert all([v['season'] for v in d['rows']]==list(range(1980,2010)) for d in pm)
p0=np.array([r['minimum_anomaly_pa'] for r in pref['rows']]);p1=np.array([[r['minimum_anomaly_pa'] for r in d['rows']] for d in pm]);assert p0.shape==(30,) and p1.shape==(10,30)
pressure_rows=[]
for cohort,idx in [('holdout',(years>=1996)&(years<=2009)),('training',(years>=1980)&(years<=1994))]:
 a=p0[idx];b=p1[:,idx].ravel()
 pressure_rows.append({'cohort':cohort,'era_n':len(a),'ace_n':len(b),'era_median_pa':float(np.median(a)),'ace_median_pa':float(np.median(b)),'era_p10_pa':float(np.quantile(a,.1)),'ace_p10_pa':float(np.quantile(b,.1))})
fig,axs=plt.subplots(1,2,figsize=(10,4))
for ax,cohort,idx in zip(axs,['holdout','training'],[(years>=1996)&(years<=2009),(years>=1980)&(years<=1994)]):
 for values,label in [(p0[idx]/100,'ERA5'),(p1[:,idx].ravel()/100,'ACE2 ten members')]:
  xx=np.sort(values);ax.step(xx,np.arange(1,len(xx)+1)/len(xx),where='post',label=f'{label} n={len(xx)}')
 ax.set(xlabel='Cold-season regional minimum surface-pressure anomaly (hPa)',ylabel='Empirical CDF',title=cohort);ax.legend();ax.grid(alpha=.3)
fig.tight_layout();fig.savefig(R/'pressure_anomaly_cdf.png',dpi=150);plt.close(fig)
(R/'decision.json').write_text(json.dumps({'verdict':verdict,'counts':counts,'excluded':['KMKE: land fraction 0.2023, lake-dominated; no replacement'],'pressure_rows':pressure_rows,'note':'Primary gate applied to seven retained pre-registered cells with original integer thresholds; pressure is auxiliary only, PRESsfc not SLP.'},indent=2,ensure_ascii=False))
print('DECISION',json.dumps({'verdict':verdict,'counts':counts,'pressure':pressure_rows},ensure_ascii=False),flush=True)
