"""Migration gate: 3 tuning objects x 2 tuning events, original vs JAX.
Does not load scoring members. CPU allocation only, no 工作站 computation.
"""
import argparse,json,time
from pathlib import Path
import numpy as np
from twin_jax import forward,metrics as jm
from method_g import Params,Plant,TUNING,LO,HI,members,init
from method_g import SRC
from plant import commands,metrics


def one(entry,event,softness):
    p=Params(**entry['params']);x=init(event)
    py=[];jv=[];valid=[];t0=time.perf_counter()
    duration=1800.;settle=120.;n=int(p.fs*duration);ns=int(p.fs*settle)
    for seed,cseed in zip((1001,1002,1003),(2001,2002,2003)):
        cmd=commands(p,float(x[0]),x[1:9],x[9:17],x[17:25],x[25:27],settle+duration,cseed)
        a=Plant(p);a.run(cmd['main'],cmd['rows'][:,:ns],cmd['terrain'],settle,sample=False)
        o=a.run(cmd['main'],cmd['rows'][:,ns:],cmd['terrain'],duration,seed=seed)
        py.append(metrics(o['series'],1/p.fs))
        out,ratio,ok=forward(p,cmd['main'],cmd['rows'],cmd['terrain'],seed,ns)
        jv.append({k:np.asarray(v) for k,v in jm(out,1/p.fs,softness).items()})
        valid.append({'numpy':o['valid'],'jax':bool(ok),'ratio_np':o['min_ratio'],'ratio_jax':float(ratio)})
    diff={}
    for key in ('u','Iu','Lux'):
        original=np.mean([row[key] for row in py],axis=0)
        transplanted=np.mean([row[key] for row in jv],axis=0)
        rel=np.abs(transplanted-original)/np.maximum(np.abs(original),1e-12)
        diff[key]={'max_rel':float(rel.max()),'mean_rel':float(rel.mean()),
                   'per_height_rel':rel.tolist(),'numpy':original.tolist(),'jax':transplanted.tolist()}
    return {'object':entry['index'],'event':event[0],'softness':softness,
            'diff':diff,'valid':valid,'wall_s':time.perf_counter()-t0}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--smoke',action='store_true');
    ap.add_argument('--softness',type=float,default=1e-4);a=ap.parse_args()
    entries=members('tuning')[:1 if a.smoke else 3]
    events=TUNING[:1 if a.smoke else 2]
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:
        for entry in entries:
            for event in events:
                row=one(entry,event,a.softness)
                row['pass']=all(row['diff'][k]['max_rel']<=v for k,v in [('u',.01),('Iu',.02),('Lux',.02)])
                f.write(json.dumps(row,allow_nan=False)+'\n');f.flush()
                print('GATE',row['object'],row['event'],row['pass'],
                      {k:round(row['diff'][k]['max_rel'],6) for k in ('u','Iu','Lux')},flush=True)
