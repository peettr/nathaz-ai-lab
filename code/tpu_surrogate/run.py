"""TPU isolated high-rise whole-building vs direction holdout, CPU Colab.
Official source https://db.wind.arch.t-kougei.ac.jp/aerodynamic/experiment/highrise/
Run: colab --auth oauth2 exec -s tpu-geometry-cp -f run.py
Raw files remain solely on Colab /content/tpu_raw; outputs in /content/tpu_out.
"""
import json, os, time, urllib.request
from pathlib import Path
import numpy as np
from scipy.io import loadmat
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from scipy.spatial.distance import cdist
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score, mean_squared_error
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RAW = Path('/content/tpu_raw'); RAW.mkdir(exist_ok=True)
OUT = Path('/content/tpu_out'); OUT.mkdir(exist_ok=True)
# All _4 = alpha 1/4; W/D and H/D deliberately varied independently.
BUILDINGS = {'T113_4': (1.,3.), 'T213_4': (2.,3.), 'T313_4': (3.,3.),
             'T212_4': (2.,2.), 'T214_4': (2.,4.)}
ANGLES = [0,10,20,30,40]
TARGET = 'T213_4'; RANDOM_WIND = 20
YKEY = ['mean', 'rms', 'min'] # min is raw record minimum, NOT return-period peak.

def load_case(b, ang):
    p = RAW / f'{b}_{ang}.mat'
    url = f'https://minio.wind.arch.t-kougei.ac.jp/web/media/case/{b}/time_series_of_point_wind_pressure_{ang}.mat'
    if not p.exists():
        print('download', url, flush=True)
        urllib.request.urlretrieve(url, p)
    d=loadmat(p)
    a=np.asarray(d['Wind_pressure_coefficients'], dtype=np.float32)
    loc=np.asarray(d['Location_of_measured_points'], dtype=float)
    assert a.shape[1]==loc.shape[1] and int(np.squeeze(d['Wind_direction_angle']))==ang
    w,h=BUILDINGS[b]
    assert np.isclose(float(np.squeeze(d['Building_breadth'])/np.squeeze(d['Building_depth'])),w,rtol=1e-4)
    assert np.isclose(float(np.squeeze(d['Building_height'])/np.squeeze(d['Building_depth'])),h,rtol=1e-4)
    # Face-local horizontal coordinate; x values are flattened facade coordinates in TPU Readme.
    x=np.empty(a.shape[1]); face=loc[3].astype(int)
    for f in range(1,5):
        idx=face==f
        xv=loc[0,idx]; x[idx]=(xv-xv.min())/(xv.max()-xv.min())
    z=loc[1]/float(np.squeeze(d['Building_height']))
    xyz=np.column_stack([face,x,z])
    y=np.column_stack([a.mean(axis=0),a.std(axis=0),a.min(axis=0)])
    return {'b':b,'angle':ang,'geom':np.array([w,h]),'xyz':xyz,'y':y,
            'n_time':a.shape[0],'frequency':int(np.squeeze(d['Sample_frequency'])),
            'size_bytes':p.stat().st_size,'url':url}

def features(c):
    xyz=c['xyz']; theta=np.deg2rad(c['angle'])
    return np.column_stack([np.full(len(xyz),c['geom'][0]),np.full(len(xyz),c['geom'][1]),
      np.full(len(xyz),np.sin(theta)),np.full(len(xyz),np.cos(theta)),
      xyz[:,1],xyz[:,2],*[ (xyz[:,0]==f).astype(float) for f in range(1,5)]])

def spatial(src, dst):
    result=np.empty((len(dst['xyz']),3))
    for f in range(1,5):
        i=src['xyz'][:,0]==f; j=dst['xyz'][:,0]==f
        x=src['xyz'][i,1:]; q=dst['xyz'][j,1:]
        lin=LinearNDInterpolator(x,src['y'][i],fill_value=np.nan)(q)
        bad=np.any(~np.isfinite(lin),axis=1)
        if bad.any(): lin[bad]=NearestNDInterpolator(x,src['y'][i])(q[bad])
        result[j]=lin
    return result

def gp_fixed(xs,ys,xq,ls):
    # Fixed SE kernel + nugget; common covariance across all tap locations/outputs.
    xs=np.asarray(xs,float)/ls; xq=np.asarray(xq,float)/ls
    k=np.exp(-0.5*cdist(xs,xs,'sqeuclidean'))
    k.flat[::len(xs)+1]+=0.03
    kt=np.exp(-0.5*cdist(xq,xs,'sqeuclidean'))
    # Constant prior mean estimated from training; avoids zero-mean Cp bias.
    mu=ys.mean(axis=0)
    return kt @ np.linalg.solve(k,ys-mu)+mu

def train_ml(cases):
    x=np.concatenate([features(c) for c in cases]); y=np.concatenate([c['y'] for c in cases])
    print('ML rows',x.shape,flush=True)
    models=[]
    for t in range(3):
        m=HistGradientBoostingRegressor(max_iter=120,max_leaf_nodes=19,
             learning_rate=0.07,l2_regularization=1,random_state=42)
        m.fit(x,y[:,t]);models.append(m);print('fit',YKEY[t],flush=True)
    return lambda c: np.column_stack([m.predict(features(c)) for m in models])

def evaluate(cases,split):
    if split=='building':
        train=[c for c in cases if c['b']!=TARGET]
        tests=[c for c in cases if c['b']==TARGET]
        # B0 width interpolation at same H/D=3 and angle; no held-out geometry used.
        def b0(c):
            a=spatial(by[( 'T113_4',c['angle'])],c)
            b=spatial(by[( 'T313_4',c['angle'])],c)
            return (a+b)/2
        def b1(c):
            sources=[by[(b,c['angle'])] for b in BUILDINGS if b!=TARGET]
            ys=np.stack([spatial(s,c) for s in sources])
            return gp_fixed([s['geom'] for s in sources],ys.reshape(len(sources),-1),
                [c['geom']],np.array([1.,1.])).reshape(-1,3)
    else:
        train=[c for c in cases if c['angle']!=RANDOM_WIND]
        tests=[c for c in cases if c['angle']==RANDOM_WIND]
        def b0(c):
            return (spatial(by[(c['b'],10)],c)+spatial(by[(c['b'],30)],c))/2
        def b1(c):
            sources=[by[(c['b'],a)] for a in ANGLES if a!=RANDOM_WIND]
            ys=np.stack([spatial(s,c) for s in sources])
            return gp_fixed([[s['angle']] for s in sources],ys.reshape(len(sources),-1),
                [[c['angle']]],np.array([14.])).reshape(-1,3)
    predict=train_ml(train)
    predictions={k:[] for k in ['B0','B1','M']}; truth=[]
    for c in tests:
        truth.append(c['y'])
        for k,fn in [('B0',b0),('B1',b1),('M',predict)]: predictions[k].append(fn(c))
    y=np.concatenate(truth); rows=[]
    for k in predictions:
        p=np.concatenate(predictions[k]); assert np.isfinite(p).all()
        row={'split':split,'method':k,'n_taps':len(y),'n_cases':len(tests)}
        for j,key in enumerate(YKEY):
            row[key+'_r2']=float(r2_score(y[:,j],p[:,j]))
            row[key+'_rmse']=float(np.sqrt(mean_squared_error(y[:,j],p[:,j])))
        rows.append(row)
    if split=='building':
        c=by[(TARGET,20)]; i=tests.index(c); plot(c,{k:predictions[k][i] for k in predictions})
    return rows

def plot(c,preds):
    f=1; mask=c['xyz'][:,0]==f; x=c['xyz'][mask,1]; z=c['xyz'][mask,2]
    vals=[c['y'][mask,0],preds['B0'][mask,0],preds['M'][mask,0]]
    vmin=min(np.min(v) for v in vals); vmax=max(np.max(v) for v in vals)
    fig,axs=plt.subplots(1,3,figsize=(11,3.5),layout='constrained')
    for ax,name,v in zip(axs,['Measured','B0 geometry linear','M gradient boosting'],vals):
        sc=ax.tricontourf(x,z,v,levels=np.linspace(vmin,vmax,19),cmap='coolwarm',vmin=vmin,vmax=vmax)
        ax.scatter(x,z,s=2,c='k',alpha=.3);ax.set_title(name)
        ax.set(xlabel='face-local x (0–1)',ylabel='z/H',xlim=(0,1),ylim=(0,1))
    fig.colorbar(sc,ax=axs,label='mean Cp'); fig.suptitle(f'TPU {TARGET}, {c["angle"]}°, nominal face 1')
    fig.savefig(OUT/'face1_mean_cp.png',dpi=170);plt.close(fig)

if __name__=='__main__':
    t=time.time(); cases=[]
    for b in BUILDINGS:
        for a in ANGLES:
            cases.append(load_case(b,a));print('loaded',b,a,cases[-1]['y'].shape,flush=True)
    by={(c['b'],c['angle']):c for c in cases}
    rows=evaluate(cases,'building')+evaluate(cases,'wind')
    (OUT/'metrics.json').write_text(json.dumps({'rows':rows,'manifest':[
       {'building':c['b'],'angle':c['angle'],'taps':len(c['y']),
        'n_time':c['n_time'],'sample_frequency_hz':c['frequency'],
        'bytes':c['size_bytes'],'url':c['url']} for c in cases],
       'elapsed_seconds':time.time()-t},indent=2))
    print('RESULT',json.dumps(rows),flush=True)
    print('ELAPSED',time.time()-t,flush=True)
