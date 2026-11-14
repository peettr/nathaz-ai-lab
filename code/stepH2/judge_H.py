# L26.12 出路 H′ 判据与否定条件计算（Lead 11-11，只读结果表）
import json, numpy as np, collections
cor=json.load(open('../step2/sae_final/correlations.json')); B=json.load(open('out/final_b_results.json'))
rows=[json.loads(l) for l in open('out/final_interventions_H.jsonl')]
prog=[json.loads(l) for l in open('out/final_intervene_progress.jsonl')]
done={p['sid'] for p in prog if p.get('stage')=='storm_done'}
rows=[r for r in rows if r['sid'] in done]
out={'storms_complete':len(done)}
# (i): main-layer best candidate by |test rho|
best=max(((p,r) for p in cor['candidates'] for r in cor['candidates'][p]),key=lambda t:abs(t[1]['test_rho']))
p,f=best[0],best[1]['feature']; diffs=[];mains=[]
for s in B['expanded'][p]:
    c=[c for c in s['candidates'] if c['feature']==f][0]; diffs.append(c['lower_abs']-s['null']['maximum']); mains.append(c['main'])
q=np.quantile(diffs,[.025,.975])
out['neg_i']=dict(attr=p,feature=f,test_rho=round(best[1]['test_rho'],4),n_seeds=len(diffs),q025=round(q[0],4),q975=round(q[1],4),min=round(min(diffs),4),max=round(max(diffs),4),main_pass=sum(mains),not_in_noise=bool(q[1]<0 or q[0]>0))
out['seed_counts']={f"{pp}/{c['feature']}":[sum(x['candidates'][k]['main'] for x in B['expanded'][pp]),sum(x['candidates'][k]['q95_read'] for x in B['expanded'][pp])] for pp in B['expanded'] for k,c in enumerate(B['expanded'][pp][0]['candidates'])}
by=collections.defaultdict(list)
for r in rows: by[(r['control'],r.get('reference',-1),r['feature'],r['alpha'])].append(r)
targets=sorted({r['feature'] for r in rows if r['control']=='target'})
sign={}
for pp in cor['candidates']:
    for r in cor['candidates'][pp]:
        if r['feature'] not in sign or abs(r['train_rho'])>abs(sign[r['feature']][1]): sign[r['feature']]=(pp,r['train_rho'])
rng=np.random.default_rng(2612); out['int']={}; out['neg_ii']={}
for j in targets:
    E={a:float(np.median([r['dmsl_hpa'] for r in by[('target',j,j,a)]])) for a in (0.,.5,1.5,2.)}
    ctrl=sorted({r['feature'] for r in rows if r['control']=='matched' and r['reference']==j})
    E0={a:float(np.quantile([abs(np.median([r['dmsl_hpa'] for r in by[('matched',j,c,a)]])) for c in ctrl],.95)) for a in (0.,2.)}
    ev=[E[a] for a in (0.,.5,1.5,2.)]; mono=bool(all(np.diff(ev)<=0) or all(np.diff(ev)>=0))
    pp,tr=sign[j]; expect=-1 if ((pp=='pres_hpa' and tr<0) or (pp=='wind_kt' and tr>0)) else 1
    direction=bool(np.sign(E[2.]-E[0.])==expect)
    ratio={a:(abs(E[a])/E0[a] if E0[a]>0 else float('inf')) for a in (0.,2.)}
    nz=sum(1 for r in by[('target',j,j,0.)] if r['dmsl_hpa']!=0)
    out['int'][j]=dict(attr=pp,E=[round(x,4) for x in ev],E0=[round(E0[0.],4),round(E0[2.],4)],ratio=[round(ratio[0.],3),round(ratio[2.],3)],mono=mono,direction=direction,
        c3=bool(direction and mono and min(ratio.values())>=3),n=len(by[('target',j,j,0.)]),nonzero_a0=nz,n_ctrl=len(ctrl),
        maxabs=round(max(abs(r['dmsl_hpa']) for a in (0.,2.) for r in by[('target',j,j,a)]),4))
    ub={}
    for a in (0.,2.):
        v=np.abs([r['dmsl_hpa'] for r in by[('target',j,j,a)]]); bs=[np.median(rng.choice(v,len(v))) for _ in range(5000)]
        ub[str(a)]=dict(median=round(float(np.median(v)),4),ub95=round(float(np.quantile(bs,.975)),4))
    out['neg_ii'][j]=ub
out['neg_ii_all_below_0.5']=bool(all(u['ub95']<0.5 for j in out['neg_ii'] for u in out['neg_ii'][j].values()))
out['diverge']={str(a):f"{sum(r.get('divergent',False) for r in rows if r['alpha']==a and r['control'] in ('target','matched','random_direction'))}/{sum(1 for r in rows if r['alpha']==a and r['control'] in ('target','matched','random_direction'))}" for a in (0.,.5,1.5,2.)}
for k in ('pure_decoder','skip_zero_effect'):
    v=[r['dmsl_hpa'] for r in rows if r['control']==k]; w=[r['dwind_ms'] for r in rows if r['control']==k]
    out[k]=dict(n=len(v),median=round(float(np.median(v)),4),median_abs=round(float(np.median(np.abs(v))),4),maxabs=round(float(max(map(abs,v))),3),n_zero=sum(1 for x in v if x==0),wind_median=round(float(np.median(w)),3))
json.dump(out,open('judge_H.json','w'),ensure_ascii=False,indent=1,default=str); print(json.dumps(out,ensure_ascii=False,default=str))
