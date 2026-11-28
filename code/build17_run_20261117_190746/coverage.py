#!/usr/bin/env python3
import json, hashlib, csv
from pathlib import Path
import numpy as np

R=Path(__file__).resolve().parent
L=R.parents[1]
P=L/'R21.4a_T5_caseE_WM_retry2/evidence/E_s102_off_thin.npz'
T=L/'tacc_feasibility/T2c_post/out_3694005/points_all_heights.json'
IDS=(31,39,40,47,48,49,65,66,69,77,79)
def sha(p):
    with p.open('rb') as f:
        h=hashlib.sha256()
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
        return h.hexdigest()
def shift(a,axis,d):
    if axis!=0:return np.roll(a,-d,axis)
    v=np.zeros_like(a)
    if d==1:v[:-1]=a[1:]
    else:v[1:]=a[:-1]
    return v

def main():
    digest=sha(P)
    assert digest==P.with_name(P.name+'.sha256').read_text().strip()
    with np.load(P,allow_pickle=False) as z:
        meta=json.loads(z['metadata'].item());fluid=z['fluid'];assert np.all((fluid==0)|(fluid==1));fluid=fluid.astype(bool)
    assert meta['k_start']==20 and meta['k_end_exclusive']==47 and meta['dims']==[500,500,270] and meta['origin']==[0.,0.,-20.] and fluid.shape==(27,500,500)
    xy=[(2,1),(2,-1),(1,1),(1,-1)];solid=~fluid
    ns=sum(shift(solid,a,d).astype('u1') for a,d in xy)
    eligible=fluid&(ns==1)&~shift(solid,0,1)&~shift(solid,0,-1)
    eligible[[0,-1]]=False   # unavailable z neighbours, not treated as solid or fluid
    actual=np.zeros_like(fluid)
    for a,d in xy:
        face=eligible&shift(solid,a,d)
        for b in {0,1,2}-{a}:
            for s in (1,-1):actual |= face&shift(face,b,s)
    # z=25 may have an additional mirror link through z=26, whose z=27 support is unknown.
    multi=fluid&(ns>=2)
    coords={int(x['id']):x['fine']['primary']['xyz_m'][:2] for x in json.loads(T.read_text()) if x['h_wall_m']==2.0}
    assert set(coords)==set(range(1,81))
    yy,xx=np.ogrid[:500,:500]; band=slice(1,7) # labels 1..6: 0..5 m above specified label 1
    rows=[]
    for i in IDS:
        x,y=coords[i]; disk=(xx-x)**2+(yy-y)**2<=100
        den=int(np.count_nonzero((fluid&(ns>=1))[band]&disk)); assert den>0
        n=int(np.count_nonzero(eligible[band]&disk)); m=int(np.count_nonzero(actual[band]&disk))
        rows.append(dict(id=i,x_m=x,y_m=y,adjacent=den,eligible=n,f_i=n/den,confirmed_paired_mirror=m,paired_f_i=m/den))
    out=dict(input=str(P),input_sha256=digest,coordinate_source=str(T),coordinate_sha256=sha(T),metadata=meta,radius_m=10,labels_in_f_i=list(range(1,7)),thin_known_eligibility_labels=[1,25],eligible_mirror_candidates=int(eligible.sum()),multi_normal_cells_z0_26=int(multi.sum()),confirmed_paired_mirror_lower_bound=int(actual.sum()),unknown_end_layer_single_normal_candidates=[int(np.count_nonzero((fluid&(ns==1))[k])) for k in (0,26)],rows=rows,f_bar=sum(x['f_i'] for x in rows)/len(rows),paired_f_bar=sum(x['paired_f_i'] for x in rows)/len(rows))
    with (R/'coverage.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
    with (R/'coverage.csv').open('x') as f:
        c=csv.DictWriter(f,fieldnames=list(rows[0]));c.writeheader();c.writerows(rows)
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
