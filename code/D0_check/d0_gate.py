import numpy as np,sys,json
d=sys.argv[1]
def co(f):
    a=np.loadtxt(f); return a[:,0],a[:,1]
r={}
tR,cR=co(d+'/co_R1.txt'); tS,cS=co(d+'/co_S2.txt')
for lo,name in [(0,'w1_(0,0.5]'),(0.25,'w2_(0.25,0.5]')]:
    mR=(tR>lo)&(tR<=0.5); mS=(tS>lo)&(tS<=0.5)
    pk=(cR[mR].max(),cS[mS].max()); p99=(np.percentile(cR[mR],99),np.percentile(cS[mS],99))
    r[name]={'peak_R1':pk[0],'peak_S2':pk[1],'peak_ok':pk[0]<=1.05*pk[1],'p99_R1':p99[0],'p99_S2':p99[1],'p99_ok':p99[0]<=1.05*p99[1]}
r['steps_R1']=len(tR); r['steps_S2_0.5s']=len(tS)
def probe(f):
    rows=[l.split() for l in open(f) if l.strip() and not l.startswith('#')]
    a=np.array([[float(x) for x in row] for row in rows]); return a
B=probe(d+'/BuildingTaps_p.txt'); R=probe(d+'/REF2_p.txt')
for nm,a in [('BuildingTaps',B),('REF2',R)]:
    v=a[:,1:]; ut=len(np.unique(a[:,0]))
    cols=v.shape[1]; fin=bool(np.isfinite(v).all())
    distinct=len({tuple(np.round(v[:,j],12)) for j in range(cols)})
    r[nm]={'frames':a.shape[0],'unique_t':ut,'cols':cols,'finite':fin,'distinct_cols':distinct}
print(json.dumps(r,indent=1,default=float))
