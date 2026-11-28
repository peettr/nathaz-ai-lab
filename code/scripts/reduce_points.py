"""Run on Colab only: turn 6-hour point series into compact seasonal/POT summaries."""
import json, sys
from pathlib import Path
import numpy as np
ROOT=Path('/content/ace_formal')
YEARS=list(range(1980,2010))
ORDER=json.loads((ROOT/'sites_frozen.json').read_text())['order']

def season(t):
    t=np.asarray(t)
    y=t.astype('datetime64[Y]').astype(int)+1970
    m=t.astype('datetime64[M]').astype(int)%12+1
    return np.where(m>=10,y,y-1)

def read(path):
    with np.load(path) as z:
        return z['time'],np.hypot(z['u'],z['v'])

def summarize(t,s,threshold):
    sy=season(t)
    result={'years':YEARS,'order':ORDER,'maxima':[],'pot_excess':[],'counts':[]}
    for y in YEARS:
        tt=np.arange(np.datetime64(f'{y}-10-01T00'),np.datetime64(f'{y+1}-04-01T00'),np.timedelta64(6,'h')).astype('datetime64[ns]')
        sl=s[sy==y]
        assert np.array_equal(t[sy==y],tt),(y,len(sl),len(tt))
        result['maxima'].append(np.max(sl,axis=0).tolist())
        result['counts'].append(len(sl))
        row=[]
        for j in range(8):
            ids=np.flatnonzero(sl[:,j]>threshold[j])
            groups=np.split(ids,np.flatnonzero(np.diff(ids)>12)+1) if len(ids) else []
            row.append([float(np.max(sl[g,j])-threshold[j]) for g in groups])
        result['pot_excess'].append(row)
    return result

mode=sys.argv[1]
if mode=='reference':
    arr=[read(ROOT/'reference'/f'cold_{y}.npz') for y in YEARS]
    t=np.concatenate([a[0] for a in arr]);s=np.concatenate([a[1] for a in arr])
    mask=np.isin(season(t),list(range(1980,1995)))
    threshold=np.quantile(s[mask],.95,axis=0).tolist()
    (ROOT/'threshold.json').write_text(json.dumps({'threshold':threshold,'source':'ERA5 conservative 0.25deg; 1980/81–1994/95 6h p95','order':ORDER}))
    result=summarize(t,s,threshold)
    (ROOT/'reference_summary.json').write_text(json.dumps(result))
    print('REFERENCE_SUMMARY_DONE',len(result['maxima']),len(t),flush=True)
else:
    m=int(mode);src=Path(sys.argv[2]);dest=Path(sys.argv[3]);assert not dest.exists()
    t,s=read(src)
    with (ROOT/'threshold.json').open() as f:threshold=json.load(f)['threshold']
    result=summarize(t,s,threshold)
    result['member']=m
    dest.write_text(json.dumps(result))
    print('MEMBER_SUMMARY_DONE',m,len(result['maxima']),flush=True)
