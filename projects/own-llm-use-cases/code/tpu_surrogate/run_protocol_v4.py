"""TPU catalog-wide 13 geometries x 5 angles, available alpha exposures; CPU Colab.
Run after uploading run_protocol_v2.py to /content: colab exec -s NAME -f run_protocol_v3.py
Outputs are new files; raw TPU data remains only in Colab. Fixed ML/GP hyperparameters.
"""
import json, time
from pathlib import Path
import numpy as np
import run_protocol_v2 as m

# Official query matrix: B:D in {1:1,2:1,3:1}; B:H = 1:1..5,
# 2:2..5, 3:2..5. Alpha=1/6 exists at B:D=1:1 and 3:1,
# including the 1:1:1 case.
m.GEOM={f'T{b}1{h}_{alpha}':(float(b),float(h))
        for b,hs in ((1,range(1,6)),(2,range(2,6)),(3,range(2,6)))
        for h in hs for alpha in ((4,6) if (b==3 or b==1) else (4,))}
m.OUT=Path('/content/tpu_out_v4'); m.OUT.mkdir(exist_ok=True)

def features(c):
    xyz=c['xyz']; t=np.deg2rad(c['ang']); n=len(xyz)
    B_over_D,H_over_D=c['geom']; D_over_B=1/B_over_D;H_over_B=H_over_D/B_over_D
    return np.column_stack([np.full(n,D_over_B),np.full(n,H_over_B),
        np.full(n,c['alpha']/10),np.full(n,np.sin(t)),np.full(n,np.cos(t)),
        xyz[:,1],xyz[:,2],*[(xyz[:,0]==f).astype(float) for f in range(1,5)]])
m.features=features

# B0/B1 geometry coordinates are D/B and H/B too, not B/D and H/D.
original=m.load_case
def load_case(b,ang):
    c=original(b,ang); c['alpha']=int(b.split('_')[-1]);
    B,H=c['geom'];c['geom']=np.array([1/B,H/B]);return c
# Original loader asserts B/D and H/D against m.GEOM; only transform afterward.

def main():
    start=time.time();cases=[]
    for b in m.GEOM:
        for ang in m.ANGLES:
            c=load_case(b,ang);cases.append(c)
            print('loaded',b,ang,len(c['y']),flush=True)
    by={(c['b'],c['ang']):c for c in cases};rows=[]
    for geom in sorted({b.split('_')[0] for b in m.GEOM}):
        tr=[c for c in cases if c['b'].split('_')[0]!=geom]
        te=[c for c in cases if c['b'].split('_')[0]==geom]
        ml=m.models_fit(tr)
        print('fit',geom,'seconds',round(time.time()-start,1),flush=True)
        for alpha in sorted({c['alpha'] for c in te}):
            t=[c for c in te if c['alpha']==alpha]
            preds={key:[] for key in ('B0','B1','GBM','MLP')};modes=[]
            for c in t:
                same=[s for s in tr if s['alpha']==alpha and s['ang']==c['ang']]
                aligned=[m.spatial(s,c) for s in same]
                b0,mode=m.geom_b0(same,c,aligned);modes.append(mode)
                val={'B0':b0,'B1':m.geom_gp(same,c,aligned),**ml(c)}
                for key in preds:preds[key].append(val[key])
                if geom=='T213' and alpha==4 and c['ang']==20:m.plot(c,val)
            truth=np.concatenate([c['y'] for c in t])
            for method,pp in preds.items():
                p=np.concatenate(pp);assert np.isfinite(p).all()
                r=dict(split='whole_geometry',building=geom,alpha=alpha,
                       group='interior' if all(v=='linear' for v in modes) else 'boundary',
                       method=method,b0_mode=modes[0],n=len(truth),**m.metrics(truth,p))
                rows.append(r);print('ROW',json.dumps(r),flush=True)
    rng=np.random.default_rng(20261013);tr=[];te=[]
    for c in cases:
        ix=rng.permutation(len(c['y']));n=max(1,int(round(.2*len(ix))))
        for target,ids in ((te,ix[:n]),(tr,ix[n:])):
            target.append({**c,'xyz':c['xyz'][ids],'y':c['y'][ids]})
    ml=m.models_fit(tr);preds={key:[] for key in ('B0_spatial','GBM','MLP')}
    for a,b in zip(tr,te):
        preds['B0_spatial'].append(m.spatial(a,b));p=ml(b)
        for key in ('GBM','MLP'):preds[key].append(p[key])
    truth=np.concatenate([c['y'] for c in te])
    for method,pp in preds.items():
        r=dict(split='random_taps',building='all',alpha='all',group='seen geometry/angle/exposure',
               method=method,n=len(truth),**m.metrics(truth,np.concatenate(pp)))
        rows.append(r);print('ROW',json.dumps(r),flush=True)
    manifest=[dict(building=c['b'],angle=c['ang'],n=len(c['y']),bytes=c['bytes'],url=c['url']) for c in cases]
    result=dict(rows=rows,manifest=manifest,elapsed_seconds=time.time()-start,
        protocol='13 geometries, all catalogued alpha combinations, five angles each, fixed hyperparameters')
    (m.OUT/'metrics_v4.json').write_text(json.dumps(result,indent=2))
    print('ELAPSED',result['elapsed_seconds'],flush=True)
if __name__=='__main__':main()
