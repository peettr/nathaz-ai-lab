"""Summarize stationary probe batches; execute on allocated CRC worker, not 工作站.
First eligible length needs >=4 statistically independent batches, and must
remain below threshold at every subsequently sampled length in the record.
"""
import argparse, json
import numpy as np

def windows(x, batch, denominator=.023):
    out=[]
    for n in range(4*batch, len(x)+1, batch):
        rows=x[:n].reshape(n//batch,batch,12)
        means=rows.mean(axis=1)
        sigmas=rows.std(axis=1,ddof=1)
        mean_se=means.std(axis=0,ddof=1)/np.sqrt(len(rows))/denominator
        sigma_se=sigmas.std(axis=0,ddof=1)/np.sqrt(len(rows))
        sigma_ref=np.maximum(x[:n].std(axis=0,ddof=1),1e-10)
        out.append({'steps':n,'max_mean_se':float(np.max(mean_se)),
                    'max_sigma_relative_se':float(np.max(sigma_se/sigma_ref))})
    for key,threshold in (('max_mean_se',.02),('max_sigma_relative_se',.05)):
        candidates=[r['steps'] for i,r in enumerate(out) if all(a[key]<=threshold for a in out[i:])]
        yield key, min(candidates) if candidates else None, out

def main():
    p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--batch',type=int,required=True)
    a=p.parse_args()
    x=np.load(a.file)
    if x.ndim!=2 or x.shape[1]!=12: raise ValueError(x.shape)
    for key,minimum,rows in windows(x,a.batch):
        print(json.dumps({'metric':key,'batch':a.batch,'T':minimum,'last':rows[-1],
                          'source':a.file,'nrows':len(rows)}))
if __name__=='__main__':main()
