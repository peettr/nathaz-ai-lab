import numpy as np,json,csv,sys
z=np.load(sys.argv[1]); taps=[r['tap_id'] for r in csv.DictReader(open(sys.argv[2]))]
y=z['y']; out={'source':sys.argv[1],'taps_index':sys.argv[2],'rule':'corr>=0.30 且 RMSE<=时均Cp RMSE（方案 v2 §1.3 关0）','points':{}}
def rc(p):
    e=float(np.sqrt(((p-y_)**2).mean())); a=p-p.mean(); b=y_-y_.mean(); return e,float((a*b).sum()/np.sqrt((a*a).sum()*(b*b).sum()))
for name in ['V2','V3','V4']:
    i=taps.index(name); y_=y[:,i]
    r={}
    for m in ['transolver','ridge','mean']:
        e,c=rc(z[m][:,i]); r[m]={'rmse':e,'corr':c if m!='mean' else None}
    r['pass']=bool(r['transolver']['corr']>=0.30 and r['transolver']['rmse']<=r['mean']['rmse'])
    out['points'][name]=r
out['gate0_pass']=all(v['pass'] for v in out['points'].values())
json.dump(out,open(sys.argv[3],'w'),ensure_ascii=False,indent=1); print(json.dumps(out,ensure_ascii=False,indent=1))
