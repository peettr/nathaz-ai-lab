"""TPU official 22 cases x all official 0..100 degree/5 degree wind directions.
CPU Colab: upload run_protocol_v2.py, run_protocol_v4.py; colab exec -f run_r2.py.
Only aggregate metrics leave Colab; raw .mat files stay on transient VM.
"""
import json, time
from pathlib import Path
import numpy as np
import run_protocol_v4 as v
m=v.m
m.ANGLES=tuple(range(0,101,5))
def official_angles(b):
    # TPU case pages: square plan T11* only 0..50; T21*/T31* 0..100.
    return tuple(range(0,51 if b.startswith('T11') else 101,5))
m.OUT=Path('/content/tpu_out_r2');m.OUT.mkdir(exist_ok=True)
# v4 overrides feature encoding/geometry; fixed hyperparameters from v2.
m.features=v.features
m.plot=lambda c,p: None  # plot separately below, no accidental older output overwrite

def main():
    start=time.time();cases=[]; rows=[]
    for b in sorted(m.GEOM):
        for a in official_angles(b):
            c=v.load_case(b,a); cases.append(c)
            print('loaded',b,a,len(c['y']),c['bytes'],flush=True)
    manifest=[dict(building=c['b'],angle=c['ang'],n=len(c['y']),bytes=c['bytes'],url=c['url']) for c in cases]
    assert len(cases)==10*11+12*21 and len({c['b'] for c in cases})==22
    (m.OUT/'manifest_r2.json').write_text(json.dumps(manifest,indent=2))
    for geom in sorted({b.split('_')[0] for b in m.GEOM}):
        tr=[c for c in cases if c['b'].split('_')[0]!=geom]
        te=[c for c in cases if c['b'].split('_')[0]==geom]
        ml=m.models_fit(tr)
        print('fit',geom,'elapsed_s',round(time.time()-start,1),flush=True)
        for alpha in sorted({c['alpha'] for c in te}):
            t=[c for c in te if c['alpha']==alpha]
            preds={k:[] for k in ('B0','B1','GBM','MLP')}; modes=[]
            for c in t:
                same=[s for s in tr if s['alpha']==alpha and s['ang']==c['ang']]
                assert len(same)>=3, (geom,alpha,c['ang'])
                aligned=[m.spatial(s,c) for s in same]
                b0,mode=m.geom_b0(same,c,aligned);modes.append(mode)
                val={'B0':b0,'B1':m.geom_gp(same,c,aligned),**ml(c)}
                for key in preds:preds[key].append(val[key])
                if geom=='T213' and alpha==4 and c['ang']==20:
                    from matplotlib import pyplot as plt
                    mask=c['xyz'][:,0]==1; x=c['xyz'][mask,1];z=c['xyz'][mask,2]
                    values=[c['y'][mask,0],val['B0'][mask,0],val['GBM'][mask,0]]
                    lo=min(q.min() for q in values);hi=max(q.max() for q in values)
                    fig,axs=plt.subplots(1,3,figsize=(11,3.5),layout='constrained')
                    for ax,name,q in zip(axs,('Measured','B0','GBM'),values):
                        h=ax.tricontourf(x,z,q,levels=np.linspace(lo,hi,19),cmap='coolwarm')
                        ax.scatter(x,z,s=2,c='k',alpha=.3)
                        ax.set(title=name,xlabel='normalized face width',ylabel='z/H',xlim=(0,1),ylim=(0,1))
                    fig.colorbar(h,ax=axs,label='mean Cp');fig.suptitle('T213_4 20°, face 1; whole-geometry holdout')
                    fig.savefig(m.OUT/'face1_mean_cp_r2.png',dpi=170);plt.close(fig)
            truth=np.concatenate([c['y'] for c in t])
            for method,pp in preds.items():
                p=np.concatenate(pp);assert np.isfinite(p).all()
                r=dict(split='whole_geometry',building=geom,alpha=alpha,
                       group='interior' if all(q=='linear' for q in modes) else 'boundary',
                       method=method,b0_mode=modes[0],n=len(truth),**m.metrics(truth,p))
                rows.append(r); print('ROW',json.dumps(r),flush=True)
        (m.OUT/'partial_r2.json').write_text(json.dumps(dict(rows=rows,manifest=manifest,elapsed_seconds=time.time()-start),indent=2))
    rng=np.random.default_rng(20261013);tr=[];te=[]
    for c in cases:
        ix=rng.permutation(len(c['y']));n=max(1,int(round(.2*len(ix))))
        for target,ids in ((te,ix[:n]),(tr,ix[n:])):
            target.append({**c,'xyz':c['xyz'][ids],'y':c['y'][ids]})
    ml=m.models_fit(tr);preds={k:[] for k in ('B0_spatial','GBM','MLP')}
    for a,b in zip(tr,te):
        preds['B0_spatial'].append(m.spatial(a,b));p=ml(b)
        for k in ('GBM','MLP'):preds[k].append(p[k])
    truth=np.concatenate([c['y'] for c in te])
    for method,pp in preds.items():
        r=dict(split='random_taps',building='all',alpha='all',group='seen geometry/angle/exposure',
               method=method,n=len(truth),**m.metrics(truth,np.concatenate(pp)))
        rows.append(r);print('ROW',json.dumps(r),flush=True)
    result=dict(rows=rows,manifest=manifest,elapsed_seconds=time.time()-start,
                protocol='13 geometries, 22 catalogued geometry-exposure cases; T11* 0..50 step 5, T21*/T31* 0..100 step 5; fixed hyperparameters')
    (m.OUT/'metrics_r2.json').write_text(json.dumps(result,indent=2))
    print('DONE',result['elapsed_seconds'],flush=True)
if __name__=='__main__':main()
