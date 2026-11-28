"""S3a-1 LBM 对照。用法: python3 -I s3a_lbm.py <out.json> <npz>..."""
import sys,json,numpy as np
UP=['P_x-30.00','P_x-25.00','P_x-20.00','P_x-15.00','P_x-10.00'];FS=50;L=3
def series(p):
    d=np.load(p);X=d['x'];ST=list(d['stations']);return [X[:,3*ST.index(f'{g}_z6')+2]*120 for g in UP]
data=[series(p) for p in sys.argv[2:]];out={}
for T in (10,20,30,60):
    n=T*FS;rows=[]
    for di,ss in enumerate(data):
        for u in ss:
            nb=len(u)//n;b=u[:nb*n].reshape(nb,n);U=b.mean(1)
            k=3*FS;c=np.cumsum(np.r_[0,u]);r3=(c[k:]-c[:-k])/k
            G=np.array([r3[i*n:(i+1)*n-k+1].max() for i in range(nb)])
            for t in range(L,nb):rows.append((di,G[t],U[t],U[t-1],U[t-2],U[t-3]))
    R=np.array(rows);res={'M':[],'MZ':[],'g':[],'y':[]}
    for di in range(len(data)):
        tr=R[:,0]!=di;te=~tr;y=R[:,1]
        for k,cols in (('M',[2]),('MZ',[2,3,4,5])):
            A=np.c_[np.ones(tr.sum()),R[tr][:,cols]];w=np.linalg.lstsq(A,y[tr],rcond=None)[0]
            res[k].append(np.c_[np.ones(te.sum()),R[te][:,cols]]@w)
        res['g'].append(R[te,2]*y[tr].sum()/R[tr,2].sum());res['y'].append(y[te])
    yy=np.concatenate(res['y']);r2=lambda p:float(1-((yy-np.concatenate(p))**2).sum()/((yy-yy.mean())**2).sum())
    o={k:r2(res[k]) for k in ('M','MZ','g')};o['n']=int(len(yy));o['d_mem']=o['MZ']-o['M'];o['noise']=1-o['MZ'];o['g_loss']=o['MZ']-o['g'];out[T]=o
    print(T,{k:round(v,4) if isinstance(v,float) else v for k,v in o.items()},flush=True)
json.dump(out,open(sys.argv[1],'w'),indent=1)
