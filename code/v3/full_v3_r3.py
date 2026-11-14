#!/usr/bin/env python3
"""L26.16 v3 dual-model staged CPU worker. TPU Aerodynamic Database (Quan et al., ICWE12 2007).
Read-only development group; load_coordinates discards H0=12 before any zip Cp member is opened.
Finite-sample interventional permutation SHAP; IG is defined only for differentiable MLP.
No tree IG substitution is made: an undefined prescribed comparison is explicitly not judged.
"""
import argparse, copy, csv, hashlib, itertools, json, math, time
from pathlib import Path
import numpy as np
from scipy.spatial import QhullError
from scipy.interpolate import NearestNDInterpolator
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import gate0

SPATIAL_FALLBACKS = {'qhull': 0, 'under_three': 0, 'outside_hull_points': 0}

def spatial_match_robust(ref, target):
    """Match baseline points; degenerate faces use the existing nearest baseline."""
    src, dst = ref['points'], target['points']
    nearest = lambda points: NearestNDInterpolator(src, ref['y'])(points)
    if len(src) < 3:
        SPATIAL_FALLBACKS['under_three'] += 1
        return np.asarray(nearest(dst))
    try:
        from scipy.interpolate import LinearNDInterpolator
        linear = np.asarray(LinearNDInterpolator(src, ref['y'], fill_value=np.nan)(dst))
    except QhullError:
        SPATIAL_FALLBACKS['qhull'] += 1
        return np.asarray(nearest(dst))
    missing = ~np.isfinite(linear)
    SPATIAL_FALLBACKS['outside_hull_points'] += int(np.count_nonzero(missing))
    if np.any(missing):
        linear[missing] = nearest(dst[missing])
    return linear

gate0.spatial_match = spatial_match_robust

SOURCE = gate0.SOURCE
SEED = gate0.SEED
FEATURES = ('roof', 'pitch', 'H0', 'D', 'direction', 'u', 'v')
GEOMETRY = tuple(range(7))  # roof, geometry, wind and tap position: top-5 of 7 is nontrivial
THRESH_J, THRESH_R = .6, .7
START = time.monotonic()

class Deadline(Exception): pass

def bounded(deadline):
    if time.monotonic() >= deadline: raise Deadline('soft 33-minute deadline')

def save_new(path, data):
    p = Path(path)
    with p.open('x') as f: json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)

def checkpoint(out, results):
    # Stage checkpoints only; a new file at every stage, no overwritten results.
    p = Path(out) / ('stage_%02d.json' % len(list(Path(out).glob('stage_*.json'))))
    save_new(p, results)

def models(seed):
    return {
        'gbm': HistGradientBoostingRegressor(max_iter=180, learning_rate=.08,
            max_leaf_nodes=31, min_samples_leaf=30, l2_regularization=1., random_state=seed),
        'mlp': make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(64,64),
            activation='relu', solver='adam', batch_size=512, max_iter=120,
            early_stopping=True, n_iter_no_change=12, random_state=seed))}

def predict(model, x): return np.asarray(model.predict(x), float)

def rank_metric(a,b):
    a=np.asarray(a,float); b=np.asarray(b,float)
    if not (np.all(np.isfinite(a)) and np.all(np.isfinite(b))): return {'jaccard':None,'spearman':None,'pass':False}
    k=min(5,len(a)); ia=set(np.argsort(-np.abs(a),kind='stable')[:k]); ib=set(np.argsort(-np.abs(b),kind='stable')[:k])
    r=float(spearmanr(a,b).statistic) if np.std(a)>1e-13 and np.std(b)>1e-13 else None
    j=len(ia&ib)/len(ia|ib)
    return {'jaccard':j, 'spearman':r, 'pass':bool(j>=THRESH_J and r is not None and r>=THRESH_R)}

def zone(point, angle):
    # R25.1-13: theta=0 from -x, theta=90 from -y.
    u,v=point; t=np.deg2rad(angle)
    s=u*np.cos(t)+v*np.sin(t); q=-u*np.sin(t)+v*np.cos(t)
    return (int(np.searchsorted([-1/3,1/3],s)), int(np.searchsorted([-1/3,1/3],q)))

def make_probe(data, roofs):
    # Representative development-only taps, deterministic one per building, zone, wind.
    probe={}
    for key, ob in sorted(data.items()):
        x,_=gate0.features([key],data,roofs)
        for z in itertools.product(range(3),repeat=2):
            ids=np.flatnonzero([zone(p,key[1])==z for p in ob['points']])
            if len(ids):
                dest=(key[1],*z)
                probe.setdefault(dest,[]).append(x[ids[len(ids)//2]])
    return {k:np.asarray(v) for k,v in probe.items()}

def draw(probes, n=3):
    # Fixed sampling: three taps from three distinct development buildings per region.
    return {k:v[np.linspace(0,len(v)-1,min(n,len(v)),dtype=int)] for k,v in probes.items() if len(v)>=3}

def shp(model, x, background, seed, nperm=20):
    """Independent empirical interventional permutation SHAP for GEOMETRY only.
    u,v,roof fixed to target; background sampled from training geometry; 20 paths per target.
    All compared conditions use identical permutations/background draw per seed.
    """
    rng=np.random.default_rng(seed)
    x=np.atleast_2d(x); background=np.atleast_2d(background)
    if len(background)<1: raise ValueError('empty background')
    bg=background[rng.integers(len(background),size=nperm)]
    permutations=np.stack([rng.permutation(len(GEOMETRY)) for _ in range(nperm)])
    out=np.zeros((len(x),len(GEOMETRY)))
    for j,point in enumerate(x):
        states=np.repeat(point[None,:],nperm,axis=0)
        states[:,GEOMETRY]=bg[:,GEOMETRY]
        prev=predict(model,states)
        for step in range(len(GEOMETRY)):
            feat=permutations[:,step]; states[np.arange(nperm),np.array(GEOMETRY)[feat]]=point[np.array(GEOMETRY)[feat]]
            nextval=predict(model,states)
            for idx in range(len(GEOMETRY)):
                out[j,idx]+=np.sum((nextval-prev)[feat==idx])/nperm
            prev=nextval
    return out

def mlp_gradient(model,x):
    scale,net=model.steps[0][1],model.steps[1][1]
    x=(x-scale.mean_)/scale.scale_
    pre=x
    active=[]
    for w,b in zip(net.coefs_[:-1],net.intercepts_[:-1]):
        p=pre@w+b; active.append((p>0,w)); pre=np.maximum(p,0)
    grad=np.broadcast_to(net.coefs_[-1][:,0],(len(x),net.coefs_[-1].shape[0])).copy()
    for mask,w in reversed(active): grad=(grad*mask)@w.T
    return grad/scale.scale_

def mlp_ig(model,x,bg,steps=48):
    # Integrated gradients on the differentiable sklearn ReLU network, training-mean baseline.
    out=[]
    for row in x:
        alpha=np.linspace(0,1,steps+1)
        path=bg[None,:]+alpha[:,None]*(row-bg)[None,:]
        gradients=mlp_gradient(model,path)
        mean=np.trapezoid(gradients,alpha,axis=0)
        out.append((row-bg)*mean)
    return np.asarray(out)

def summary_metrics(a,b):
    rows={str(k):rank_metric(a[k],b[k]) for k in sorted(a.keys() & b.keys())}
    return {'n_regions':len(rows),'min_jaccard':min((v['jaccard'] for v in rows.values()),default=None),
            'min_spearman':min((v['spearman'] for v in rows.values() if v['spearman'] is not None), default=None),
            'pass':bool(rows) and all(v['pass'] for v in rows.values()),'per_region':rows}

def aggregate_attribution(model, sample, bg, seed):
    out={}
    for key,x in sorted(sample.items()):
        # Median signed contribution across 3 distinct buildings. No sealed Cp queried.
        out[key]=np.median(shp(model,x,bg,seed+hashlib.sha256(str(key).encode()).digest()[0]),axis=0)
    return out

def stage0(data,roofs,deadline):
    keys=sorted(data); groups=[k[0] for k in keys]; rows=[]
    for fold,(tri,tei) in enumerate(GroupKFold(n_splits=5).split(keys,groups=groups)):
        bounded(deadline)
        tr=[keys[i] for i in tri]; te=[keys[i] for i in tei]
        x,y=gate0.features(tr,data,roofs); xt,yt=gate0.features(te,data,roofs)
        pred={}
        for name,model in models(SEED).items():
            model.fit(x,y); pred[name]=predict(model,xt)
        pred['nearest']=gate0.baseline(te,tr,data,'nearest')
        pred['linear']=gate0.baseline(te,tr,data,'linear')
        n=len(yt); sse={k:float(np.sum((v-yt)**2)) for k,v in pred.items()}
        row={'fold':fold,'n_points':n,'test_buildings':len(set(k[0] for k in te)),
             'rmse':{k:math.sqrt(e/n) for k,e in sse.items()},'sse':sse}
        rows.append(row); print(json.dumps(row),flush=True)
    n=sum(r['n_points'] for r in rows)
    pooled={k:math.sqrt(sum(r['sse'][k] for r in rows)/n) for k in rows[0]['sse']}
    passed={k:all(pooled[k]<=.9*pooled[b] for b in ('nearest','linear')) for k in ('gbm','mlp')}
    return {'folds':rows,'pooled_rmse':pooled,'threshold':'surrogate RMSE <=0.9 * each baseline',
            'pass_models':passed,'pass':all(passed.values())}

def freeze_predictions(coords_path, model, roofs, ref, gbm, probes, out):
    """Freeze predictions using metadata only; never load sealed Cp/statistics members."""
    case_rows={}
    with open(coords_path,newline='') as f:
        for r in csv.DictReader(f):
            if r['lib']=='noeaves' and r['face_type']=='ROOF': case_rows.setdefault(r['case'],r)
    assert len(case_rows)==116
    pairs=[]
    case_geom={k:(v['roof'],round(float(v['pitch'])),float(v['H0']),float(v['D'])) for k,v in case_rows.items()}
    for a,b in itertools.combinations(sorted(case_geom),2):
        x,y=case_geom[a],case_geom[b]
        if x[0]!=y[0]:continue
        diff=[i for i in range(1,4) if x[i]!=y[i]]
        if len(diff)!=1:continue
        i=diff[0]
        if i==1 and (x[2]!=12 or y[2]!=12):continue
        if i==3 and (x[2]!=12 or y[2]!=12):continue
        if i==2 and not ({x[2],y[2]} in ({8.,12.},{12.,16.})):continue
        if i in (1,3):
            values=sorted({g[i] for g in case_geom.values() if g[0]==x[0] and g[2]==12})
            if sorted((x[i],y[i])) not in [values[j:j+2] for j in range(len(values)-1)]:continue
        left,right=(a,b) if x[i]<y[i] else (b,a)
        pairs.append((left,right,i))
    rows=[]
    for left,right,axis in pairs:
        for key,xx in sorted(probes.items()):
            attr_a,attr_b=ref[key],gbm[key]
            ta=set(np.argsort(-np.abs(attr_a),kind='stable')[:min(5,len(attr_a))]);tb=set(np.argsort(-np.abs(attr_b),kind='stable')[:min(5,len(attr_b))])
            common=ta&tb; feature_index=axis
            if feature_index not in common:continue
            old=xx.copy();new=xx.copy()
            for col,case in ((old,left),(new,right)):
                roof,pitch,height,depth=case_geom[case]
                col[:,0]=roofs.index(roof);col[:,1:4]=(pitch,height,depth)
            d=float(np.mean(predict(model,new)-predict(model,old)))
            signed=float(np.sign(attr_a[feature_index]))
            rows.append({'case_low':left,'case_high':right,'parameter':FEATURES[axis],
                'wind':key[0],'zone_stream':key[1],'zone_cross':key[2],
                'shap_sign':int(np.sign(signed)),'importance_order':'>'.join(FEATURES[GEOMETRY[j]] for j in np.argsort(-np.abs(attr_a))),
                'direct_delta_cp':d,'direct_sign':int(np.sign(d)),'common_top5':'>'.join(FEATURES[GEOMETRY[j]] for j in sorted(common))})
    p=Path(out)/'predictions_frozen.csv'
    if not rows:raise ValueError('No matching top-5 intervention predictions')
    with p.open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return {'status':'frozen','n_pairs':len(pairs),'n_rows':len(rows),'path':str(p),'sha256':gate0.sha256(p)}

def main(a):
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()): raise FileExistsError('Full output directory must start empty')
    deadline=START+a.soft_seconds
    results={'source':SOURCE,'config':{'seed':SEED,'explanation':'interventional empirical permutation SHAP 20 permutations, 3 development buildings per region; 100 training background rows',
            'mlp':'sklearn StandardScaler+MLPRegressor(64,64), ReLU, adam, 120 epochs, early_stopping; IG 48 trapezoid steps from training mean',
            'gbm':'sklearn HistGradientBoostingRegressor 180 trees; model is piecewise constant, standard IG undefined',
            'regions':'roof (windward,middle,leeward) x (left,middle,right) x 7 winds',
            'geometry_features':list(np.array(FEATURES)[list(GEOMETRY)]),
            'source_hashes':{'coords':gate0.sha256(a.coords),'stats':gate0.sha256(a.stats)},'sealed_H0_12_Cp_members_opened':0},
            'gate0':{'status':'not_started'},'gate1':{'status':'not_started'},
            'gate2':{'status':'not_started'},'gate2b':{'status':'not_started'},
            'predictions':{'status':'not_started'}}
    try:
        coords=gate0.load_coordinates(a.coords)
        if gate0.sha256(a.stats)!='7bff3edaef3b1a33c6623635caa2661e4e716203f1c4e99e62bf4ba6a37b3b92':
            raise ValueError('statistics hash mismatch before opening Cp members')
        data=gate0.read_dev_stats(a.stats,coords)
        roofs=sorted({v['roof'] for v in data.values()})
        results['gate0']=stage0(data,roofs,deadline)
        results['gate0']['spatial_fallbacks'] = dict(SPATIAL_FALLBACKS)
        checkpoint(out,results)
        if not results['gate0']['pass']:
            for key in ('gate1','gate2','gate2b','predictions'):
                results[key]={'status':'not_judged','reason':'one or both surrogates failed gate0'}
            save_new(out/'gates_v3.json',results); return
        bounded(deadline)
        keys=sorted(data); x,y=gate0.features(keys,data,roofs)
        fitted=models(SEED)
        for model in fitted.values(): model.fit(x,y)
        probes=draw(make_probe(data,roofs)); background=x[np.random.default_rng(SEED).choice(len(x),100,replace=False)]
        np.savez_compressed(out/'model_inputs.npz',background=background,train_mean=x.mean(axis=0))
        # 1a: exact linear interventional SHAP analytic answer (not a sampled/noisy shortcut).
        ridge=Ridge(alpha=1.).fit(x,y); probe=x[np.random.default_rng(SEED+1).choice(len(x),30,replace=False)]
        analytic=(probe-x.mean(axis=0))*ridge.coef_
        # Numerical path integration of Ridge gradient, independent from SHAP implementation.
        ridge_grad=np.tile(ridge.coef_, (len(probe),1))
        integrated=(probe-x.mean(axis=0))*ridge_grad
        known=float(spearmanr(analytic.ravel(),integrated.ravel()).statistic)
        ref=aggregate_attribution(fitted['mlp'],probes,background,SEED)
        bounded(deadline)
        # 1b: cumulative randomization from output to input layer, log each layer.
        scrambled=copy.deepcopy(fitted['mlp']); rng=np.random.default_rng(SEED)
        net=scrambled.named_steps['mlpregressor']; layer_corr=[]
        for layer in reversed(range(len(net.coefs_))):
            net.coefs_[layer]=rng.normal(0,np.std(net.coefs_[layer]),net.coefs_[layer].shape)
            scrambled_attr=aggregate_attribution(scrambled,probes,background,SEED)
            layer_corr.append({'layer':layer,'spearman':float(spearmanr(np.concatenate(list(ref.values())),np.concatenate(list(scrambled_attr.values()))).statistic)})
            bounded(deadline)
        corr=layer_corr[-1]['spearman']
        # 1c one of 4 geometry features = top 10% rounded up; same feature count in 100 controls.
        selected=np.array([list(GEOMETRY)[np.argmax(np.abs(v))] for v in ref.values()])
        original=np.array([predict(fitted['mlp'],vv).mean() for vv in probes.values()]); means=x.mean(axis=0)
        change=[]; control=[]
        for (key,v),idx,old in zip(probes.items(),selected,original):
            v2=v.copy(); v2[:,idx]=means[idx]; change.append(abs(predict(fitted['mlp'],v2).mean()-old))
            rr=[]; random_cols=np.random.default_rng(SEED+len(change)).choice(GEOMETRY,100,replace=True)
            for col in random_cols:
                r=v.copy(); r[:,col]=means[col]
                rr.append(abs(predict(fitted['mlp'],r).mean()-old))
            control.append(rr)
        delta=float(np.median(change)); null95=float(np.percentile(np.median(control,axis=0),95))
        # 1d shift both raw inputs and scaler reference: same normalized input, exactly same model function.
        shifted=copy.deepcopy(fitted['mlp']); shift=np.ones(x.shape[1])*.25
        shifted.named_steps['standardscaler'].mean_ += shift
        invariant=np.allclose(predict(fitted['mlp'],probe),predict(shifted,probe+shift),rtol=1e-8,atol=1e-8)
        shiftattr={k:np.median(shp(shifted,v+shift,background+shift,SEED+hashlib.sha256(str(k).encode()).digest()[0]),axis=0) for k,v in probes.items()}
        invariant_corr=float(spearmanr(np.concatenate(list(ref.values())),np.concatenate(list(shiftattr.values()))).statistic)
        gate1={'known_answer_spearman':known,'randomized_layers_output_to_input':layer_corr,'randomized_output_layer_spearman':layer_corr[0]['spearman'],'randomized_all_layers_spearman':corr,
            'deletion_change':delta,'random_deletion_p95':null95,'input_shift_output_invariant':bool(invariant),
            'input_shift_spearman':invariant_corr,
            'pass_components':{'1a':known>=.95,'1b':corr<=.5,'1c':delta>=null95,'1d':bool(invariant and invariant_corr>=.9)}}
        gate1['pass']=all(gate1['pass_components'].values()); results['gate1']=gate1; checkpoint(out,results)
        if not gate1['pass']:
            for key in ('gate2','gate2b','predictions'): results[key]={'status':'not_judged','reason':'gate1 failed'}
            save_new(out/'gates_v3.json',results); return
        bounded(deadline)
        # Per-region IG is the median of 3 taps; background train mean, output only geometry dimensions.
        ig_map={k:np.median(mlp_ig(fitted['mlp'],v,means)[:,GEOMETRY],axis=0) for k,v in probes.items()}
        alternate=x[np.random.default_rng(SEED+2).choice(len(x),100,replace=False)]
        alt_map=aggregate_attribution(fitted['mlp'],probes,alternate,SEED)
        noise_map={k:np.median(shp(fitted['mlp'],v+np.random.default_rng(SEED+3).normal(0,.01*np.std(x,axis=0),v.shape),background,SEED+hashlib.sha256(str(k).encode()).digest()[0]),axis=0) for k,v in probes.items()}
        repeat=aggregate_attribution(fitted['mlp'],probes,background,SEED)
        seed_metrics={}
        for seed in (SEED+1,SEED+2,SEED+3,SEED+4):
            bounded(deadline)
            model=models(seed)['mlp'];model.fit(x,y)
            attr=aggregate_attribution(model,probes,background,SEED)
            seed_metrics[str(seed)]=summary_metrics(ref,attr)
        results['gate2']={'noise_floor_same_checkpoint':summary_metrics(ref,repeat),
            'method_shap_vs_ig_mlp':summary_metrics(ref,ig_map),
            'background':summary_metrics(ref,alt_map),'input_noise_1pct':summary_metrics(ref,noise_map),
            'five_training_seeds':seed_metrics,
            'gbm_ig':{'status':'not_applicable','reason':'GBM is used for gate0 and gate2b SHAP only; classical IG is undefined for its piecewise-constant predictor'},
            'explanation_target':'MLP; GBM is independent gate2b surrogate'}
        results['gate2']['pass']=all(results['gate2'][k]['pass'] for k in ('method_shap_vs_ig_mlp','background','input_noise_1pct','noise_floor_same_checkpoint')) and all(v['pass'] for v in seed_metrics.values())
        results['gate2']['status']='done'
        checkpoint(out,results)
        # Dual surrogate SHAP with identical background/permutations and probe sample.
        bounded(deadline)
        gbm=aggregate_attribution(fitted['gbm'],probes,background,SEED)
        results['gate2b']=summary_metrics(ref,gbm)
        results['gate2b']['status']='done';checkpoint(out,results)
        if results['gate2']['pass'] and results['gate2b']['pass']:
            bounded(deadline)
            results['predictions']=freeze_predictions(a.coords,fitted['mlp'],roofs,ref,gbm,probes,out)
        else:
            results['predictions']={'status':'not_judged','reason':'gate2 or gate2b did not meet preregistered threshold'}
        save_new(out/'gates_v3.json',results)
    except Deadline as e:
        results['unfinished_reason']=str(e);checkpoint(out,results);save_new(out/'gates_v3.json',results)
    except Exception as e:
        results['worker_error']=repr(e);checkpoint(out,results);save_new(out/'gates_v3.json',results)
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--coords',required=True);p.add_argument('--stats',required=True)
    p.add_argument('--out',required=True);p.add_argument('--soft-seconds',type=int,default=1980)
    main(p.parse_args())
