"""Lead verdict check (11-15 18:20), archived after review 5f78e443. Produced LEAD_VERDICT_CHECK_20261115.txt.
Note: in that run 'unreliable' used ||FD1%-FD0.5%||/||FD0.5%||; final convention is /||FD1%|| (classification identical)."""
import json,ast,numpy as np
def arr(x): return np.array(json.loads(x) if isinstance(x,str) else x,float)
def d(x): return ast.literal_eval(x) if isinstance(x,str) else x
R=[json.loads(l) for l in open('run_01m/stage2/stage2_results.jsonl')]+[json.loads(l) for l in open('run_01o/addendum_results.jsonl')]
fd={};ad={}
for r in R:
  if r.get('type') in ('result','fd_result') and (r.get('dtype','float64')=='float64'):
    fd[(r['metric'],r['point'],r['T'],r['fd_step_fraction'])]=arr(r['fd'])
    ad.setdefault((r['metric'],r['point'],r['T']),arr(r['ad']))
def cr(a,b): return float(a@b/np.linalg.norm(a)/np.linalg.norm(b)), float(np.linalg.norm(a-b)/np.linalg.norm(b))
for m,T in (('mean',4480),('mean',8960),('mean',17920),('mean',35840),('var',9280),('var',18560),('var',37120),('var',74240)):
  rel=[];passes=0
  for p in range(5):
    f1=fd.get((m,p,T,0.01)); f5=fd.get((m,p,T,0.005)); a=ad.get((m,p,T))
    if f1 is None or f5 is None or a is None: continue
    u=np.linalg.norm(f1-f5)/np.linalg.norm(f5); c,rd=cr(a,f1)
    if u<=.05: rel.append(p); passes+=(c>=.95 and rd<=.1)
  n=len(rel); need=int(np.ceil(.8*n)) if n else 0
  print(m,T,rel,passes,need,'不判' if n<3 else ('梯度准' if passes>=need else '梯度不准'))
