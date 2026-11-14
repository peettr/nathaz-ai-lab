# L26.12-03 判据与否定条件计算（Lead 11-03，只读结果表）
import json, numpy as np, collections
C='chain_out/'
cor=json.load(open(C+'correlations.json')); B=json.load(open(C+'b_results.json'))
rows=[json.loads(l) for l in open(C+'interventions.jsonl')]
out={'corr':{},'neg_i':{},'int':{},'neg_ii':{},'diverge':{}}
null=cor['null']; base=cor['baselines']
for p in ('wind_kt','pres_hpa'):
    pca=abs(base[p]['pca_test_rho'])
    for r in cor['candidates'][p]:
        lo,hi=r['test_ci95']; lb=0 if lo<=0<=hi else min(abs(lo),abs(hi)); m=abs(r['test_rho'])
        out['corr'][f"{p}/{r['feature']}"]=dict(test_rho=round(r['test_rho'],4),lb=round(lb,4),main=bool(m>=.5 and lb>null[p]['max_200']),q95=bool(m>=.5 and lb>null[p]['q95_200']),c2=bool(m>=pca))
    out['corr'][p+'_null']=dict(max=round(null[p]['max_200'],4),q95=round(null[p]['q95_200'],4),pca=round(pca,4),ridge=round(base[p]['ridge_test_rho'],4))
# (i): best main-reading candidate = max |test rho| over both attrs
best=max(((p,r) for p in cor['candidates'] for r in cor['candidates'][p]),key=lambda t:abs(t[1]['test_rho']))
p,f=best[0],best[1]['feature']; diffs=[];mains=[];q95s=[]
for s in B['expanded'][p]:
    c=[c for c in s['candidates'] if c['feature']==f][0]
    diffs.append(c['lower_abs']-s['null']['maximum']); mains.append(c['main']); q95s.append(c['q95_read'])
q=np.quantile(diffs,[.025,.975])
out['neg_i']=dict(attr=p,feature=f,diff_q025=round(q[0],4),diff_q975=round(q[1],4),min=round(min(diffs),4),max=round(max(diffs),4),main_pass_seeds=sum(mains),q95_pass_seeds=sum(q95s),not_in_noise=bool(q[1]<0 or q[0]>0))
# per-attr seed summary for all candidates
seedsum={}
for pp in B['expanded']:
    for s in B['expanded'][pp]:
        for c in s['candidates']:
            k=f"{pp}/{c['feature']}"; seedsum.setdefault(k,[0,0]); seedsum[k][0]+=c['main']; seedsum[k][1]+=c['q95_read']
out['seed_pass_counts_main_q95']=seedsum
# interventions
by=collections.defaultdict(list)
for r in rows: by[(r['control'],r.get('reference',-1),r['feature'],r['alpha'])].append(r)
targets=sorted({r['feature'] for r in rows if r['control']=='target'})
rng=np.random.default_rng(2612)
train_sign={}
for pp in cor['candidates']:
    for r in cor['candidates'][pp]:
        if r['feature'] not in train_sign or abs(r['train_rho'])>abs(train_sign[r['feature']][1]): train_sign[r['feature']]=(pp,r['train_rho'])
for j in targets:
    E={a:float(np.median([r['dmsl_hpa'] for r in by[('target',j,j,a)]])) for a in (0.,.5,1.5,2.)}
    ctrl=sorted({r['feature'] for r in rows if r['control']=='matched' and r['reference']==j})
    E0={a:float(np.quantile([abs(np.median([r['dmsl_hpa'] for r in by[('matched',j,c,a)]])) for c in ctrl],.95)) for a in (0.,2.)}
    ev=[E[a] for a in (0.,.5,1.5,2.)]; mono=all(np.diff(ev)<=0) or all(np.diff(ev)>=0)
    pp,tr=train_sign[j]
    # feature larger -> stronger storm: pres rho<0 means feature up -> pressure down; alpha 2 should lower MSL if rho_pres<0 ; wind rho>0 means stronger -> lower MSL too
    expect_sign = -1 if ((pp=='pres_hpa' and tr<0) or (pp=='wind_kt' and tr>0)) else 1   # sign of E(2)-E(0)
    direction=bool(np.sign(E[2.]-E[0.])==expect_sign)
    ratio={a:(abs(E[a])/E0[a] if E0[a]>0 else float('inf')) for a in (0.,2.)}
    c3=bool(direction and mono and min(ratio.values())>=3)
    out['int'][j]=dict(attr=pp,E=[round(x,4) for x in ev],E0=[round(E0[0.],4),round(E0[2.],4)],ratio=[round(ratio[0.],3),round(ratio[2.],3)],mono=bool(mono),direction=direction,c3=c3,n=len(by[('target',j,j,0.)]),
        maxabs=round(max(abs(r['dmsl_hpa']) for a in (0.,2.) for r in by[('target',j,j,a)]),4))
    ub={}
    for a in (0.,2.):
        v=np.abs([r['dmsl_hpa'] for r in by[('target',j,j,a)]]); bs=[np.median(rng.choice(v,len(v))) for _ in range(5000)]
        ub[a]=dict(median=round(float(np.median(v)),4),ub95=round(float(np.quantile(bs,.975)),4))
    out['neg_ii'][j]=ub
out['neg_ii_all_below_0.5']=bool(all(u['ub95']<0.5 for j in out['neg_ii'] for u in out['neg_ii'][j].values()))
out['diverge']={str(a):f"{sum(r.get('divergent',False) for r in rows if r['alpha']==a and r['control']!='pure_decoder')}/{sum(1 for r in rows if r['alpha']==a and r['control']!='pure_decoder')}" for a in (0.,.5,1.5,2.)}
pd=[r['dmsl_hpa'] for r in rows if r['control']=='pure_decoder']; out['pure_decoder']=dict(n=len(pd),median=round(float(np.median(pd)),4),maxabs=round(float(max(map(abs,pd))),3))
out['n_rows']=len(rows); out['storms']=len({r['sid'] for r in rows})
json.dump(out,open('judge_A.json','w'),ensure_ascii=False,indent=1,default=str); print(json.dumps(out,ensure_ascii=False,indent=1,default=str))
