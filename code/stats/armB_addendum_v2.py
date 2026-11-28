"""Post-review addendum (11-15, after rc-review 5f78e443). Descriptive/secondary items the plan §2.2 required but armB_stats.py omitted:
 1) secondary comparisons per plan: G vs A3, G vs A1, Holm at total 0.05, same verdict rule as main;
 2) f' parallel reading: f'_k(o,e) = min(f_k, min over methods incl. G and seeds of e_k), S recomputed for all; main verdict still uses f.
Usage: python3 armB_addendum_v2.py <L30.1f results.jsonl> <f_final.jsonl> <G results.jsonl>"""
import json,sys,numpy as np
sys.path.insert(0,__file__.rsplit('/',1)[0]); import armB_stats as A
base=[json.loads(l) for l in open(sys.argv[1])]; f=A.load_f(sys.argv[2])
G=[dict(r,method='G') for r in map(json.loads,open(sys.argv[3]))]
out={}
def run(fd,tag):
  S={m:A.per_object(base,fd,m) for m in ('A1','A2','A3')}; SG=A.per_object(G,fd,'G')
  r={'median_S':{**{m:float(np.median(list(v.values()))) for m,v in S.items()},'G':float(np.median(list(SG.values())))}}
  r['main_G_vs_A2']=A.compare(S['A2'],SG,'A2','G',.01)
  sec=[A.compare(S[m],SG,m,'G',.05) for m in ('A3','A1')]
  order=np.argsort([c['p'] for c in sec]); stop=False
  for rank,i in enumerate(order):
    thr=.05/(len(sec)-rank)
    if stop: thr=-1
    c=A.compare(S[sec[i]['A']],SG,sec[i]['A'],'G',thr if thr>0 else 1e-300); c['holm_alpha']=thr if thr>0 else 'stopped'
    if sec[i]['p']>=thr: stop=True
    sec[i]=c
  r['secondary_holm']=sec; out[tag]=r
run(f,'f_original')
fp={}
for k,v in f.items():
  if v is None: fp[k]=None; continue
  es=[np.array(r['e'],float) for r in base+G if (r['object'],r['event'])==k and 'e' in r]
  fp[k]=np.minimum(v,np.min(es,axis=0)) if es else v
lower=sum(1 for r in G if f.get((r['object'],r['event'])) is not None and np.any(np.array(r['e'])<f[(r['object'],r['event'])]))
out['G_rows_with_any_e_below_f']=lower
run(fp,'f_prime')
print(json.dumps(out,indent=1,ensure_ascii=False))
