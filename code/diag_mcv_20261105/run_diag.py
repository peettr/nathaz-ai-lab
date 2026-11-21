"""Post-hoc L31.9c diagnostics; run ONLY on Colab CPU, inputs in /content/diag/input."""
import csv, json, math, os
from pathlib import Path
import numpy as np
from scipy.stats import pearsonr, spearmanr, gumbel_r

ROOT=Path('/content/diag'); I=ROOT/'input'; O=ROOT/'out'; O.mkdir(exist_ok=True,parents=True)
N=2000; B=5000; SEED=20261016; G=float(np.euler_gamma); C=float(np.sqrt(6)/np.pi)
K10=float(-np.log(-np.log(0.9))-G)
def loadcsv(p): return list(csv.DictReader((I/p).open()))
def loadjsonl(p): return [json.loads(x) for x in (I/p).read_text().splitlines()]
def savecsv(p,rows):
 with (O/p).open('x',newline='') as f:
  w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
def dump(p,x): (O/p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False))
def fit(v):
 a=np.asarray(v,float);m=float(a.mean());s=float(a.std(ddof=0));cv=s/m;beta=s*C;mu=m;u=m-G*beta;x10=m+K10*beta
 assert np.isclose(x10,m+K10*beta)
 return dict(m=m,s=s,CV=cv,mu=mu,u=u,beta=beta,x10=x10)
def ss(y,z):return 1-float(np.mean(y)/np.mean(z))
def rcalc(a,b):return float(pearsonr(a,b).statistic),float(spearmanr(a,b).statistic)
versions=['final2','sens_q3pk']; old={v:loadcsv(v+'/station_params.csv') for v in versions}; oldlos={v:loadcsv(v+'/loso_results.csv') for v in versions}; dec={v:json.loads((I/(v+'/decision.json')).read_text()) for v in versions};
obs={v:{(r['station'],r['season_year']):r for r in loadjsonl(v+'/qc_station_seasons.jsonl')} for v in versions}
era={x['season_year']:x['stations'] for x in loadjsonl('sens_q3pk/era_seasons.jsonl')}
meta={r['station']:r for r in loadcsv('sens_q3pk/static_gates.csv')}; names=[x['station'] for x in old['final2']];assert len(names)==29 and set(names)=={x['station'] for x in old['sens_q3pk']}
original={v:{x['station']:x for x in old[v]} for v in versions}
losmap={v:{r['station']:r for r in oldlos[v]} for v in versions}
# A: original scoring rows, exact score convention.
rep={v:ss([np.log(float(r['R10']))**2 for r in oldlos[v]],[np.log(float(r['R10_base']))**2 for r in oldlos[v]]) for v in versions}
for v,target in [('final2',.39192),('sens_q3pk',.22662)]:
 assert len(oldlos[v])==29 and abs(rep[v]-target)<1e-4 and abs(rep[v]-dec[v]['SS'])<1e-10,(v,rep[v],dec[v]['SS'])
print('A_REPRODUCED',rep,flush=True)
station=[]; arrays={}; earrays={}; params={v:{} for v in versions}; changed=[]
for v in versions:
 for st in names:
  ys=json.loads(original[v][st]['seasons']);sy=[obs[v][st,y]['qc_peak']['kn'] for y in ys];ey=[era[y][st]['ace1_max_mps'] for y in ys]
  a=fit(sy);e=fit(ey);params[v][st]=a;arrays[v,st]=dict(zip(ys,sy));earrays[v,st]=dict(zip(ys,ey))
  for side,p,unit in [('station',a,'kn'),('ERA5',e,'m/s')]:
   station.append(dict(version=v,station=st,region=original[v][st]['region'],side=side,unit=unit,n=len(ys),**p))
  row=original[v][st]; assert np.isclose(a['mu'],float(row['station_mu_kn']),atol=1e-9) and np.isclose(e['beta'],float(row['era_beta_mps']),atol=1e-9)
for st in names:
 a=params['final2'][st];b=params['sens_q3pk'][st];dm=math.log(b['m']/a['m']);dc=math.log((1+K10*C*b['CV'])/(1+K10*C*a['CV']));dx=math.log(b['x10']/a['x10']);assert abs(dx-dm-dc)<1e-12
 changed.append(dict(station=st,delta_log_x10=dx,delta_log_m=dm,delta_log_CV_term=dc,x10_final=a['x10'],x10_sens=b['x10']))
# C: score using identical LOSO roster and 200 km exclusion from frozen scorer.
def hav(a,b):
 p,q=np.deg2rad([float(a['lat']),float(b['lat'])]);dl=np.deg2rad(float(a['lon'])-float(b['lon']));h=np.sin((p-q)/2)**2+np.cos(p)*np.cos(q)*np.sin(dl/2)**2
 return 12742*np.arcsin(np.sqrt(h))
def evaluate(kind):
 rows=[]
 for st in names:
  if kind=='S0': src=params['final2'][st]
  elif kind=='S1':src=params['sens_q3pk'][st]
  else:
   a=params['final2'][st];b=params['sens_q3pk'][st];m=b['m'] if kind=='H_m' else a['m'];cv=a['CV'] if kind=='H_m' else b['CV'];src=fit_from(m,cv)
  train=[t for t in names if t!=st and hav(meta[st],meta[t])>200];assert len(train)==len(json.loads(losmap['final2'][st]['train_stations']))
  def hp(t):
   if kind=='S0':return params['final2'][t]
   if kind=='S1':return params['sens_q3pk'][t]
   a=params['final2'][t];b=params['sens_q3pk'][t];return fit_from(b['m'] if kind=='H_m' else a['m'],a['CV'] if kind=='H_m' else b['CV'])
  pred=[]
  for p in ('mu','beta'):
   x=np.array([float(original['final2'][t]['era_'+p+'_mps']) for t in train]);y=np.array([hp(t)[p] for t in train]);coeff=np.linalg.lstsq(np.column_stack([np.ones(len(x)),x]),y,rcond=None)[0];pred.append(float(np.array([1,float(original['final2'][st]['era_'+p+'_mps'])])@coeff))
  xpred=pred[0]+pred[1]*K10;base=np.mean([hp(t)['x10'] for t in train]);actual=src['x10'];assert min(xpred,base,actual)>0
  rows.append(dict(version=kind,station=st,region=original['final2'][st]['region'],numerator=float(np.log(xpred/actual)**2),denominator=float(np.log(base/actual)**2),R10=float(xpred/actual),R10_base=float(base/actual)))
 return rows
def fit_from(m,cv):
 s=cv*m;beta=s*C;return dict(m=m,s=s,CV=cv,mu=m,u=m-G*beta,beta=beta,x10=m+K10*beta)
scored={k:evaluate(k) for k in ('S0','S1')}
for v,k in [('final2','S0'),('sens_q3pk','S1')]:
 assert abs(ss([r['numerator'] for r in scored[k]],[r['denominator'] for r in scored[k]])-rep[v])<1e-10
 for a,b in zip(scored[k],oldlos[v]): assert a['station']==b['station'] and abs(a['R10']-float(b['R10']))<1e-10,(k,a,b)
print('A_FULL_SCORER_PARITY',rep,flush=True)
scored.update({k:evaluate(k) for k in ('H_m','H_CV')})
savecsv('station_mcv.csv',station);savecsv('x10_log_decomposition.csv',changed)
score={k:ss([r['numerator'] for r in vv],[r['denominator'] for r in vv]) for k,vv in scored.items()};sh_m=((score['H_m']-score['S0'])+(score['S1']-score['H_CV']))/2;sh_cv=((score['H_CV']-score['S0'])+(score['S1']-score['H_m']))/2
assert abs(sh_m+sh_cv-(score['S1']-score['S0']))<1e-12
srows=[dict(version=k,SS=score[k],mean_num=float(np.mean([r['numerator'] for r in vv])),mean_den=float(np.mean([r['denominator'] for r in vv])),shapley_m=sh_m if k=='S1' else '',shapley_CV=sh_cv if k=='S1' else '') for k,vv in scored.items()];savecsv('ss_decomposition.csv',srows)
contrib=[]
for idx,st in enumerate(names):
 a=scored['S0'][idx];b=scored['S1'][idx];contrib.append(dict(station=st,delta_num=b['numerator']-a['numerator'],delta_den=b['denominator']-a['denominator'],num_final=a['numerator'],num_sens=b['numerator'],den_final=a['denominator'],den_sens=b['denominator']))
savecsv('ss_station_contributions.csv',contrib)
jack=[]
for j,st in enumerate(names):
 x=ss([r['numerator'] for i,r in enumerate(scored['S0']) if i!=j],[r['denominator'] for i,r in enumerate(scored['S0']) if i!=j]);y=ss([r['numerator'] for i,r in enumerate(scored['S1']) if i!=j],[r['denominator'] for i,r in enumerate(scored['S1']) if i!=j]);jack.append(dict(omitted=st,SS_final=x,SS_sens=y,delta=y-x))
savecsv('ss_jackknife.csv',jack)
rng=np.random.default_rng(SEED);diff=[]
for _ in range(N):
 ix=rng.integers(0,29,29);v=[ss([scored[k][i]['numerator'] for i in ix],[scored[k][i]['denominator'] for i in ix]) for k in ('S0','S1')];diff.append(v[1]-v[0])
# D: paired season block across stations; only available seasons per station.
variables=('beta','CV','m','mu'); raw={v:{} for v in versions}; corrs=[];boot={};lambda_rows=[]; rng=np.random.default_rng(SEED)
for v in versions:
 for p in variables:
  sx=np.array([params[v][st][p] for st in names]);gx=np.array([fit([earrays[v,st][y] for y in earrays[v,st]])[p] for st in names]);raw[v,p]=(sx,gx)
  rp,rs=rcalc(sx,gx);corrs.append(dict(version=v,variable=p,pearson=rp,spearman=rs))
 # Draw shared seasonal index once for all variables and both sides.
 indexed={p:(np.empty((B,29)),np.empty((B,29))) for p in variables}
 for i in range(B):
  draws=rng.choice(list(range(2007,2022)),size=15,replace=True)
  for j,st in enumerate(names):
   y=[z for z in draws if z in arrays[v,st]];assert len(y)>=2
   a=fit([arrays[v,st][z] for z in y]);e=fit([earrays[v,st][z] for z in y]);
   for p in variables:indexed[p][0][i,j]=a[p];indexed[p][1][i,j]=e[p]
 for p in variables:
  a,b=indexed[p];rp,rs=rcalc(*raw[v,p]);rboot=np.array([rcalc(a[i],b[i]) for i in range(B)]);boot[v,p]=rboot
  pv=np.var(a,axis=0,ddof=1);qv=np.var(b,axis=0,ddof=1);va=float(np.var(raw[v,p][0],ddof=1));vb=float(np.var(raw[v,p][1],ddof=1));la=max(0.,1-float(np.mean(pv))/va);lb=max(0.,1-float(np.mean(qv))/vb)
  corrected=rp/math.sqrt(la*lb) if p in ('beta','CV') and min(la,lb)>=.2 else None
  lambda_rows.append(dict(version=v,variable=p,observed_r=rp,pearson_ci_low=float(np.quantile(rboot[:,0],.05)),pearson_ci_high=float(np.quantile(rboot[:,0],.95)),spearman_ci_low=float(np.quantile(rboot[:,1],.05)),spearman_ci_high=float(np.quantile(rboot[:,1],.95)),lambda_station=la,lambda_ERA5=lb,mean_sampling_var_station=float(np.mean(pv)),mean_sampling_var_ERA5=float(np.mean(qv)),cross_station_var_station=va,cross_station_var_ERA5=vb,corrected_r=corrected if corrected is not None else '不可校正'))
  if p=='beta':
   # independent sites and seasons; fixed observed means, moment estimates from simulated samples.
   ta=va-float(np.mean(pv));tb=vb-float(np.mean(qv));
   for rho in (0,.25,.5,.75):
    if min(ta,tb)<=0:
     lambda_rows.append(dict(version=v,variable='simulation_beta',observed_r=rp,rho=rho,status='不成立：去噪真方差非正'))
     continue
    simrng=np.random.default_rng(SEED+int(rho*1000)+(0 if v=='final2' else 10000));sim=np.empty(B)
    # Observed station mean mu fixed; cross-site beta truth centered at observed beta means; truncate positive draws
    means=np.array([params[v][s]['mu'] for s in names]);emeans=np.array([fit(list(earrays[v,s].values()))['mu'] for s in names]);ba=np.mean(raw[v,p][0]);bb=np.mean(raw[v,p][1]);
    for z in range(B):
     z1=simrng.normal(size=29);z2=simrng.normal(size=29);truea=np.maximum(.001,ba+np.sqrt(ta)*z1);trueb=np.maximum(.001,bb+np.sqrt(tb)*(rho*z1+np.sqrt(1-rho*rho)*z2));
     one=simrng.gumbel(means[:,None]-G*truea[:,None],truea[:,None],size=(29,15));two=simrng.gumbel(emeans[:,None]-G*trueb[:,None],trueb[:,None],size=(29,15));sim[z]=np.corrcoef(one.std(axis=1)*C,two.std(axis=1)*C)[0,1]
    lambda_rows.append(dict(version=v,variable='simulation_beta',rho=rho,observed_r=rp,sim_p05=float(np.quantile(sim,.05)),sim_p50=float(np.median(sim)),sim_p95=float(np.quantile(sim,.95)),observed_percentile=float(np.mean(sim<=rp)),status='ok',true_var_station=ta,true_var_ERA5=tb))
savecsv('corr_noise.csv',[{**{k:'' for k in set().union(*(x.keys() for x in lambda_rows))},**x} for x in lambda_rows])
savecsv('corr_raw.csv',corrs)
rjack=[]
for v in versions:
 for p in variables:
  x,y=raw[v,p]
  for j,st in enumerate(names):
   a,b=rcalc(np.delete(x,j),np.delete(y,j));rjack.append(dict(version=v,variable=p,omitted=st,pearson=a,spearman=b))
savecsv('corr_jackknife.csv',rjack)
summary={'A':rep,'C':{'SS':score,'shapley_m':sh_m,'shapley_CV':sh_cv,'delta_ci90':np.quantile(diff,[.05,.95]).tolist(),'jackknife':{k:[min(r[k] for r in jack),max(r[k] for r in jack)] for k in ('SS_final','SS_sens','delta')}},'D_correlations':corrs,'input_counts':{'stations':len(names),'seasons':len(era),'bootstrap_C':N,'bootstrap_D':B}}
dump('summary.json',summary)
print('COMPLETE',json.dumps(summary,ensure_ascii=False),flush=True)
