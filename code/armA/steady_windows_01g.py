"""Batch-mean window qualification on post-spinup observations (GPU node)."""
import argparse,json
import numpy as np

def evaluate(a,batch):
    rows=[]
    for n in range(4*batch,len(a)+1,batch):
        chunks=a[:n].reshape(-1,batch,12)
        m=chunks.mean(axis=1); s=chunks.std(axis=1,ddof=1)
        mean_se=m.std(axis=0,ddof=1)/np.sqrt(len(chunks))/.05
        sigma_se=s.std(axis=0,ddof=1)/np.sqrt(len(chunks))
        sigma_ref=np.maximum(a[:n].std(axis=0,ddof=1),1e-10)
        rows.append(dict(steps=n,max_mean_se=float(mean_se.max()),
            max_sigma_relative_se=float((sigma_se/sigma_ref).max())))
    result={}
    for key,threshold in [('max_mean_se',.02),('max_sigma_relative_se',.05)]:
        valid=[v['steps'] for i,v in enumerate(rows) if all(r[key]<=threshold for r in rows[i:])]
        result[key]=min(valid) if valid else None
    return dict(stage='windows',T_m=result['max_mean_se'],T_v=result['max_sigma_relative_se'],
                batch=batch,denominator_mean=.05,last=rows[-1] if rows else None,
                rows=rows)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--batch',type=int,default=1920)
    x=p.parse_args(); data=np.load(x.file)
    assert data.ndim==2 and data.shape[1]==12
    print(json.dumps(evaluate(data,x.batch)))
