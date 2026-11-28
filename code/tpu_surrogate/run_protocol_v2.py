"""TPU high-rise Cp, fixed five-geometry/five-angle CPU Colab protocol v2.
Run: colab --auth oauth2 exec -s tpu-logo-v2 -f run_protocol_v2.py
Source: https://db.wind.arch.t-kougei.ac.jp/aerodynamic/experiment/highrise/
Raw data only on Colab; no held-out pressure used in fitting, scaling or selection.
"""
import json, time, urllib.request
from pathlib import Path
import numpy as np
from scipy.io import loadmat
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from scipy.spatial import Delaunay, QhullError
from scipy.spatial.distance import cdist
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import r2_score
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RAW=Path('/content/tpu_raw'); RAW.mkdir(exist_ok=True)
OUT=Path('/content/tpu_out_v2'); OUT.mkdir(exist_ok=True)
GEOM={'T113_4':(1.,3.),'T213_4':(2.,3.),'T313_4':(3.,3.),'T212_4':(2.,2.),'T214_4':(2.,4.)}
ANGLES=(0,10,20,30,40)
SEED=42

def load_case(b,ang):
    p=RAW/f'{b}_{ang}.mat'
    url=f'https://minio.wind.arch.t-kougei.ac.jp/web/media/case/{b}/time_series_of_point_wind_pressure_{ang}.mat'
    if not p.exists():
        print('download',url,flush=True)
        urllib.request.urlretrieve(url,p)
    d=loadmat(p); a=np.asarray(d['Wind_pressure_coefficients'],dtype=np.float32)
    loc=np.asarray(d['Location_of_measured_points'],dtype=float)
    assert a.shape[1]==loc.shape[1] and int(np.squeeze(d['Wind_direction_angle']))==ang
    breadth=float(np.squeeze(d['Building_breadth'])); depth=float(np.squeeze(d['Building_depth']))
    height=float(np.squeeze(d['Building_height']))
    assert np.allclose((breadth/depth,height/depth),GEOM[b],rtol=1e-4)
    face=loc[3].astype(int); x=np.empty(len(face))
    for f in range(1,5):
        mask=face==f; v=loc[0,mask]; x[mask]=(v-v.min())/(v.max()-v.min())
    xyz=np.column_stack([face,x,loc[1]/height])
    y=np.column_stack([a.mean(axis=0),a.std(axis=0)]).astype(float)
    del a,d
    return dict(b=b,ang=ang,geom=np.array(GEOM[b]),xyz=xyz,y=y,url=url,bytes=p.stat().st_size)

def features(c):
    xyz=c['xyz']; t=np.deg2rad(c['ang']); n=len(xyz)
    return np.column_stack([np.full(n,c['geom'][0]),np.full(n,c['geom'][1]),
        np.full(n,np.sin(t)),np.full(n,np.cos(t)),xyz[:,1],xyz[:,2],
        *[(xyz[:,0]==f).astype(float) for f in range(1,5)]])

def spatial(src,dst):
    out=np.empty((len(dst['xyz']),2))
    for f in range(1,5):
        i=src['xyz'][:,0]==f; j=dst['xyz'][:,0]==f
        xy=src['xyz'][i,1:]; q=dst['xyz'][j,1:]
        if len(xy)>=3:
            try: val=LinearNDInterpolator(xy,src['y'][i],fill_value=np.nan)(q)
            except QhullError: val=np.full((len(q),2),np.nan)
        else: val=np.full((len(q),2),np.nan)
        bad=~np.isfinite(val).all(axis=1)
        if bad.any(): val[bad]=NearestNDInterpolator(xy,src['y'][i])(q[bad])
        out[j]=val
    return out

def geom_b0(train,c,aligned):
    g=np.stack([s['geom'] for s in train]); q=c['geom']; vals=np.stack(aligned)
    try: inside=Delaunay(g).find_simplex(q)>=0
    except QhullError: inside=False
    if inside:
        v=LinearNDInterpolator(g,vals.reshape(len(g),-1))(q)
        if np.isfinite(v).all(): return v.reshape(len(c['y']),2),'linear'
    ix=np.argmin(np.linalg.norm(g-q,axis=1))
    return vals[ix],'nearest (B0 undefined: extrapolation)'

def geom_gp(train,c,aligned):
    g=np.stack([s['geom'] for s in train]); q=c['geom'][None,:]
    # Fixed geometry length-scale (1,1), nugget 0.03, training-only prior mean.
    k=np.exp(-.5*cdist(g,g,'sqeuclidean')); k.flat[::len(g)+1]+=.03
    kt=np.exp(-.5*cdist(q,g,'sqeuclidean'))
    ys=np.stack(aligned).reshape(len(g),-1); mu=ys.mean(axis=0)
    return (kt @ np.linalg.solve(k,ys-mu)+mu).reshape(len(c['y']),2)

def models_fit(train):
    x=np.concatenate([features(c) for c in train]); y=np.concatenate([c['y'] for c in train])
    gb=[]
    for j in range(2):
        m=HistGradientBoostingRegressor(max_iter=120,max_leaf_nodes=19,
             learning_rate=.07,l2_regularization=1,random_state=SEED)
        m.fit(x,y[:,j]); gb.append(m)
    # Scale x and each y using training rows only. Fixed architecture, no tuning.
    xs=StandardScaler().fit(x); ys=StandardScaler().fit(y)
    nn=MLPRegressor(hidden_layer_sizes=(64,64),max_iter=130,early_stopping=True,
          n_iter_no_change=12,random_state=SEED,learning_rate_init=.001)
    nn.fit(xs.transform(x),ys.transform(y))
    return lambda c: {'GBM':np.column_stack([m.predict(features(c)) for m in gb]),
                       'MLP':ys.inverse_transform(nn.predict(xs.transform(features(c))))}

def metrics(y,p):
    return {k+'_'+metric: float(fn(y[:,j],p[:,j])) for j,k in enumerate(('mean','rms'))
            for metric,fn in [('r2',r2_score),('rmse',lambda a,b:np.sqrt(np.mean((a-b)**2))) ]}

def plot(c,pred):
    mask=c['xyz'][:,0]==1; x=c['xyz'][mask,1]; z=c['xyz'][mask,2]
    vals=[c['y'][mask,0],pred['B0'][mask,0],pred['GBM'][mask,0]]
    lo=min(v.min() for v in vals); hi=max(v.max() for v in vals)
    fig,axs=plt.subplots(1,3,figsize=(11,3.5),layout='constrained')
    for ax,name,v in zip(axs,('Measured','B0 geometry linear','GBM'),vals):
        h=ax.tricontourf(x,z,v,levels=np.linspace(lo,hi,19),cmap='coolwarm')
        ax.scatter(x,z,s=2,c='k',alpha=.3)
        ax.set(title=name,xlabel='face x / width',ylabel='z / H',xlim=(0,1),ylim=(0,1))
    fig.colorbar(h,ax=axs,label='mean Cp')
    fig.suptitle('TPU T213_4 20 degrees face 1; leave whole geometry out')
    fig.savefig(OUT/'face1_mean_cp_v2.png',dpi=170);plt.close(fig)

def main():
    start=time.time(); cases=[]
    for b in GEOM:
        for ang in ANGLES:
            c=load_case(b,ang);cases.append(c)
            print('loaded',b,ang,len(c['y']),flush=True)
    by={(c['b'],c['ang']):c for c in cases}; rows=[]
    for held in GEOM:
        tr=[c for c in cases if c['b']!=held]; te=[c for c in cases if c['b']==held]
        ml=models_fit(tr); print('fit complete',held,'seconds',round(time.time()-start,1),flush=True)
        pred={m:[] for m in ('B0','B1','GBM','MLP')}; base_modes=[]
        for c in te:
            same=[by[(b,c['ang'])] for b in GEOM if b!=held]
            aligned=[spatial(s,c) for s in same]
            b0,mode=geom_b0(same,c,aligned);base_modes.append(mode)
            values={'B0':b0,'B1':geom_gp(same,c,aligned),**ml(c)}
            for m,p in values.items(): pred[m].append(p)
            if held=='T213_4' and c['ang']==20: plot(c,values)
        truth=np.concatenate([c['y'] for c in te]); split='interior' if all(x=='linear' for x in base_modes) else 'boundary'
        for m in pred:
            p=np.concatenate(pred[m]);assert np.isfinite(p).all()
            row=dict(split='whole_geometry',building=held,group=split,method=m,
                     b0_mode=base_modes[0],n=len(truth),**metrics(truth,p))
            rows.append(row); print('ROW',json.dumps(row),flush=True)
    # Random tap split within each geometry-angle case; exact same case represented in train.
    rng=np.random.default_rng(20261013); tr=[];te=[]
    for c in cases:
        perm=rng.permutation(len(c['y'])); n=max(1,int(round(.2*len(perm))))
        for target,ix in ((tr,perm[n:]),(te,perm[:n])):
            target.append({**c,'xyz':c['xyz'][ix], 'y':c['y'][ix]})
    ml=models_fit(tr); randpred={m:[] for m in ('B0_spatial','GBM','MLP')}
    for a,b in zip(tr,te):
        randpred['B0_spatial'].append(spatial(a,b))
        pp=ml(b)
        for m in ('GBM','MLP'): randpred[m].append(pp[m])
    truth=np.concatenate([c['y'] for c in te])
    for m,pp in randpred.items():
        row=dict(split='random_taps',building='all',group='seen geometries/angles',
                 method=m,n=len(truth),**metrics(truth,np.concatenate(pp)))
        rows.append(row);print('ROW',json.dumps(row),flush=True)
    manifest=[dict(building=c['b'],angle=c['ang'],n=len(c['y']),bytes=c['bytes'],url=c['url']) for c in cases]
    result=dict(rows=rows,manifest=manifest,elapsed_seconds=time.time()-start,
                protocol='five pre-selected geometries, all five selected angles; alpha=1/4 only; fixed hyperparameters')
    (OUT/'metrics_v2.json').write_text(json.dumps(result,indent=2))
    print('ELAPSED',result['elapsed_seconds'],flush=True)
if __name__=='__main__':main()
