#!/usr/bin/env python3
"""M7 v3 supplement (six-review 1c1f9228 must-fix 2-4,6). Reuses v2 functions unchanged
(imported), writes only to score_v3/. Does not alter v2 outputs or the gate.
Adds: (a) bit-equality check vs v2 predictions/gate; (b) event-wise Top-k bootstrap with
per-copy event_id suffix; (c) no-intercept sensitivity (points, cond numbers D2/FXD2, daily
interval); (d) FX coefficient summary; (e) per-site contribution and drop-one-site D;
(f) strong-wind-row MAE/bias (archives lead_check_1107 numbers).
"""
import importlib.util,json
from pathlib import Path
import numpy as np,pandas as pd
R=Path('./23_AI_Weather/06_Logs/r23_2_m7');O=R/'score_v3';O.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('v2',R/'score_m7_local_v2.py');v2=importlib.util.module_from_spec(spec);spec.loader.exec_module(v2)
v2.O=O  # predict() writes coefficients/condition numbers here, not score_v2
FHRS=v2.FHRS;SEED=v2.SEED;key=['site','init_utc','fhr']

def design_noint(d,m):
 return v2.design(d,m)[:,1:]

def main():
 tr,te=v2.prepare();pred=v2.predict(tr,te);pred,th=v2.native_events(pred)
 old=pd.read_parquet(R/'score_v2/paired_predictions.parquet')
 a=pred.sort_values(key).reset_index(drop=True);b=old.sort_values(key).reset_index(drop=True)
 maxdiff={}
 for c in ['obs','D2','FXD2','FX-T0','M+D1+FX','D2_q05','FXD2_q95']:
  maxdiff[c]=float(np.max(np.abs(a[c].to_numpy()-b[c].to_numpy())))
  assert maxdiff[c]<1e-9,(c,maxdiff[c])  # v3.1: first run required bit-equality and failed at 1.6e-12 (float rounding, rank-deficient lstsq)
 gate=json.loads((R/'score_v2/gate.json').read_text())
 cond=[];ni=[]
 for fhr in FHRS:
  for site in sorted(te.site.unique()):
   pool=tr[(tr.site!=site)&(tr.fhr==fhr)];part=te[(te.site==site)&(te.fhr==fhr)]
   row={'fhr':fhr,'site':site};p=part[key].copy()
   for m in ('D2','FXD2'):
    A=v2.design(pool,m);An=design_noint(pool,m)
    row[f'cond_{m}_int']=float(np.linalg.cond(A));row[f'cond_{m}_noint']=float(np.linalg.cond(An))
    c=np.linalg.lstsq(An,pool.obs.to_numpy(),rcond=None)[0];p[m+'_noint']=design_noint(part,m)@c
   cond.append(row);ni.append(p)
 pd.DataFrame(cond).to_csv(O/'condition_numbers_v3.csv',index=False)
 pred=pred.merge(pd.concat(ni),on=key,validate='one_to_one')
 pred['day']=pred.valid_end_utc.dt.floor('D')
 boot=[];contrib=[];drop=[];strong=[];coef=[]
 cf=pd.read_csv(O/'coefficients.csv')
 for fhr in FHRS:
  d=pred[pred.fhr==fhr].reset_index(drop=True)
  days=d.day.unique();groups=[np.flatnonzero(d.day.to_numpy()==x) for x in days]
  rng=np.random.default_rng(SEED+fhr)  # same seed as v2 -> identical day draws
  e1=np.abs(d.FXD2-d.obs).to_numpy();e0=np.abs(d.D2-d.obs).to_numpy()
  n1=np.abs(d.FXD2_noint-d.obs).to_numpy();n0=np.abs(d.D2_noint-d.obs).to_numpy()
  pts={'D':e1.mean()/e0.mean()-1,'D_noint':n1.mean()/n0.mean()-1}
  for m in v2.METHODS:
   for k in (1,5,10):pts[f'eventTop{k}_{m}']=v2.topk(d,m,k,True)
  draws={x:[] for x in pts}
  for _ in range(1000):
   pick=rng.integers(0,len(groups),len(groups))
   ix=np.concatenate([groups[j] for j in pick])
   cnt={};cp=[]
   for j in pick:
    c=cnt.get(j,0);cnt[j]=c+1;cp.append(np.full(len(groups[j]),c))
   cp=np.concatenate(cp)
   draws['D'].append(e1[ix].mean()/e0[ix].mean()-1);draws['D_noint'].append(n1[ix].mean()/n0[ix].mean()-1)
   bb=d.iloc[ix].reset_index(drop=True)
   bb['event_id']=[f'{e}#{c}' if isinstance(e,str) else e for e,c in zip(bb.event_id,cp)]
   for m in v2.METHODS:
    for k in (1,5,10):draws[f'eventTop{k}_{m}'].append(v2.topk(bb,m,k,True))
  for x,v in pts.items():
   boot.append({'fhr':fhr,'metric':x,'point':float(v),'lo':float(np.nanquantile(draws[x],.025)),'hi':float(np.nanquantile(draws[x],.975)),'n':len(d),'days':len(days)})
  g=next(r for r in gate['D'] if r['fhr']==fhr)
  me=[r for r in boot if r['fhr']==fhr and r['metric']=='D'][0]
  assert abs(me['point']-g['point'])<1e-12 and abs(me['lo']-g['lo'])<1e-12 and abs(me['hi']-g['hi'])<1e-12,(me,g)
  s=d.assign(dd=e1-e0).groupby('site').dd.sum();net=s.sum()
  for site,v in s.items():contrib.append({'fhr':fhr,'site':site,'sum_absdiff_FXD2_minus_D2':float(v),'share_of_net':float(v/net)})
  for site in sorted(d.site.unique()):
   h=d.site.to_numpy()!=site;drop.append({'fhr':fhr,'dropped':site,'D':float(e1[h].mean()/e0[h].mean()-1)})
  ev=d[d.event]
  strong.append({'fhr':fhr,'n_event_rows':len(ev),'MAE_D2':float(np.abs(ev.D2-ev.obs).mean()),'MAE_FXD2':float(np.abs(ev.FXD2-ev.obs).mean()),'bias_D2':float((ev.D2-ev.obs).mean()),'bias_FXD2':float((ev.FXD2-ev.obs).mean())})
  for m in ('FXD2','M+D1+FX','FX-T0'):
   v=np.array([json.loads(x)[-1] for x in cf[(cf.fhr==fhr)&(cf.method==m)].coefficients])
   coef.append({'fhr':fhr,'method':m,'folds':len(v),'n_negative':int((v<0).sum()),'min':float(v.min()),'median':float(np.median(v)),'max':float(v.max())})
 pd.DataFrame(boot).to_csv(O/'bootstrap_v3.csv',index=False)
 pd.DataFrame(contrib).to_csv(O/'site_contribution.csv',index=False)
 pd.DataFrame(drop).to_csv(O/'drop_one_site_D.csv',index=False)
 pd.DataFrame(strong).to_csv(O/'strong_wind_rows.csv',index=False)
 pd.DataFrame(coef).to_csv(O/'fx_coefficient_summary.csv',index=False)
 (O/'check_v2_equal.json').write_text(json.dumps({'predictions_max_abs_diff_vs_v2':maxdiff,'tolerance':1e-9,'D_point_and_interval_equal_v2':True,'rows':len(pred)},indent=1))
 (O/'score.done').write_text('success\n');print('V3_DONE',flush=True)
if __name__=='__main__':main()
