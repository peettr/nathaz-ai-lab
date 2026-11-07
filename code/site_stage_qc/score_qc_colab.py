"""Frozen v2 spatial LOSO Gumbel moment mapping; Colab only."""
import csv,json,math,datetime as dt
from pathlib import Path
from collections import defaultdict
import numpy as np
root=Path('/content/site_stage_qc');adm=list(csv.DictReader((root/'station_admission.csv').open()));stations=[r for r in adm if r['admitted']=='true']; qc=list(map(json.loads,(root/'qc_station_seasons.jsonl').read_text().splitlines())); assert len(qc)==435 and not any('error' in r for r in qc); eligible={st for st in (r['station'] for r in stations) if sum(v['station']==st and v['valid'] for v in qc)>=12}; stations=[r for r in stations if r['station'] in eligible]; print('QC_ADMISSION',len(stations),sorted(eligible),flush=True)
assert all(sum(r['region']==g for r in stations)>=8 for g in ('plains','other')), '站数不足: do not run score'
obs={}
for x in map(json.loads,(root/'qc_station_seasons.jsonl').read_text().splitlines()):obs[x['station'],x['season_year']]=x
era={x['season_year']:x['stations'] for x in map(json.loads,(root/'era_seasons.jsonl').read_text().splitlines())}
assert len(era)==15 and all((s['station'],y) in obs and s['station'] in era[y] for s in stations for y in range(2007,2022))
G=float(np.euler_gamma)
def moments(a):
 a=np.asarray(a,float);mu=float(a.mean());beta=float(a.std(ddof=0)*np.sqrt(6)/np.pi)
 return mu,beta
def return_value(mu,b,T):return float(mu+b*(-np.log(-np.log(1-1/T))-G))
def hav(a,b):
 p,q=np.deg2rad([float(a['lat']),float(b['lat'])]);dl=np.deg2rad(float(a['lon'])-float(b['lon']));h=np.sin((p-q)/2)**2+np.cos(p)*np.cos(q)*np.sin(dl/2)**2
 return 12742*np.arcsin(np.sqrt(h))
meta={r['station']:r for r in csv.DictReader((root/'static_gates.csv').open())}
params=[]
for s in stations:
 st=s['station'];ys=[y for y in range(2007,2022) if obs[st,y]['valid']];sy=np.array([obs[st,y]['qc_peak']['kn'] for y in ys]);ey=np.array([era[y][st]['ace1_max_mps'] for y in ys]);sm,sb=moments(sy);em,eb=moments(ey)
 row={'station':st,'region':s['region'],'n':len(ys),'seasons':json.dumps(ys),'station_mu_kn':sm,'station_beta_kn':sb,'era_mu_mps':em,'era_beta_mps':eb}
 for T in (10,50):row[f'station_x{T}_kn']=return_value(sm,sb,T);row[f'era_x{T}_mps']=return_value(em,eb,T)
 params.append(row)
def save_csv(path,rows):
 with (root/path).open('x',newline='') as f:w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
save_csv('station_params.csv',params)
results=[]
for h in params:
 st=h['station'];train=[q for q in params if q['station']!=st and hav(meta[st],meta[q['station']])>200]
 assert len(train)>=2,(st,len(train))
 pred={}
 for p in ('mu','beta'):
  x=np.array([q[f'era_{p}_mps'] for q in train]);y=np.array([q[f'station_{p}_kn'] for q in train]);A=np.column_stack([np.ones(len(x)),x]);c=np.linalg.lstsq(A,y,rcond=None)[0];pred[p]=float(np.array([1,h[f'era_{p}_mps']])@c);pred[p+'_intercept']=float(c[0]);pred[p+'_slope']=float(c[1])
 row={'station':st,'region':h['region'],'train_count':len(train),'train_stations':json.dumps([q['station'] for q in train]),'pred_mu_kn':pred['mu'],'pred_beta_kn':pred['beta'],'mu_intercept':pred['mu_intercept'],'mu_slope':pred['mu_slope'],'beta_intercept':pred['beta_intercept'],'beta_slope':pred['beta_slope']}
 for T in (10,50):
  actual=h[f'station_x{T}_kn'];p=return_value(pred['mu'],pred['beta'],T);base=float(np.mean([q[f'station_x{T}_kn'] for q in train]));row.update({f'pred_x{T}_kn':p,f'obs_x{T}_kn':actual,f'R{T}':p/actual,f'base_x{T}_kn':base,f'R{T}_base':base/actual})
 results.append(row)
save_csv('loso_results.csv',results)
for r in results:
 if r['R10']<=0 or r['R10_base']<=0:raise ValueError(('undefined log ratio; do not adjust method',r['station']))
rng=np.random.default_rng(20261016)
def metric(sub):
 z=np.asarray([np.log(r['R10'])**2 for r in sub]);b=np.asarray([np.log(r['R10_base'])**2 for r in sub]);return 1-float(z.mean()/b.mean()),float(np.mean([abs(r['R10']-1)<=.15 for r in sub]))
ss,hit=metric(results);boot=[]
for i in range(2000):
 sub=[results[k] for k in rng.integers(0,len(results),size=len(results))];boot.append(metric(sub))
bs=np.array(boot);ci=np.quantile(bs,[.05,.95],axis=0).T
regional={}
for g in ('plains','other'):
 group=[r for r in results if r['region']==g];ss0,h=metric(group);rng2=np.random.default_rng(20261016);bb=np.array([metric([group[k] for k in rng2.integers(0,len(group),size=len(group))]) for _ in range(2000)])
 regional[g]={'n':len(group),'hit_count':sum(abs(r['R10']-1)<=.15 for r in group),'hit_rate':h,'SS':ss0,'SS_ci90':np.quantile(bb[:,0],[.05,.95]).tolist(),'hit_ci90':np.quantile(bb[:,1],[.05,.95]).tolist()}
median=float(np.median([abs(r['R50']-1) for r in results]));passed=(hit>=.7 and all(regional[g]['hit_rate']>=.6 for g in regional) and ss>.1 and ci[0][0]>0 and median<=.2);failed=(hit<.5 or ci[0][1]<=0)
status='通过' if passed else '不通过' if failed else '说不清'
decision={'status':status,'n':len(results),'hit_count':int(sum(abs(r['R10']-1)<=.15 for r in results)),'hit_rate':hit,'SS':ss,'SS_ci90':ci[0].tolist(),'hit_ci90':ci[1].tolist(),'median_abs_R50_minus_1':median,'regional':regional,'thresholds':{'pass_hit_total':.7,'pass_hit_each_region':.6,'pass_SS':.1,'pass_SS_ci_lower':0,'pass_median_abs_R50':.2,'fail_hit_total_below':.5,'fail_SS_ci_upper_at_most':0},'created_edt':dt.datetime.now(dt.timezone(dt.timedelta(hours=-4))).isoformat()}
(root/'decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2));print('DECISION',json.dumps(decision,ensure_ascii=False),flush=True)
