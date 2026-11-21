"""Method G on frozen L30.1f v8b: tuning objects only; no scoring members.

The frozen plant evaluates every candidate. The differentiable nominal twin sees only
median tuning parameters, fixed command phases, and a constant measured-minus-model
residual. This module does not import scoring.json or reference candidates.
"""
import json,time
from dataclasses import replace
from pathlib import Path
import numpy as np
import jax
import jax.numpy as jnp
from twin_jax import forward,metrics

HERE=Path(__file__).resolve().parent
SRC=HERE/'from_L30.1f'
import sys
sys.path.insert(0,str(SRC/'q1'))
from common import Params,Plant,TUNING,LO,HI,target,errors,normalized,members
from methods import init,measure,SCHEDULE
from tune import official


def nominal_params():
    entries=members('tuning')
    from dataclasses import fields
    return Params(**{f.name:float(np.median([e['params'][f.name] for e in entries])) for f in fields(Params)})


def signal_bases(fs,duration,seed):
    n=int(round(duration*fs)); rng=np.random.default_rng(seed)
    phase=rng.uniform(0,2*np.pi,n//2+1);phase[0]=0
    if n%2==0:phase[-1]=0
    return jnp.asarray(np.fft.rfftfreq(n,1/fs)),jnp.asarray(np.exp(1j*phase))


def jax_command(x,p,duration,seed,bases=None):
    """Exact plant.commands spectrum, phase and per-row standardization (JAX)."""
    freq,phasor=signal_bases(p.fs,duration,seed) if bases is None else bases
    n=int(round(duration*p.fs))
    spectral=(1+(freq[None,:]*x[17:25,None]/6)**2)**(-5/12)
    spectral=spectral.at[:,0].set(0)
    waves=jnp.fft.irfft(spectral*phasor[None,:],n=n,axis=-1)
    waves=waves/jnp.std(waves,axis=-1,keepdims=True)
    rows=jnp.clip(x[1:9,None]+x[9:17,None]*waves,-17,20)
    return rows


def metric_vec(m):return jnp.concatenate((m['u'],m['Iu'],m['Lux']))


def objective(x,p,event,measured,pred0,window_s,seed=911,command_seed=2001,
              softness=1e-4,checkpoint=True,bases=None):
    """Measured statistics anchor at current x0; stop_gradient constant residual.

    Predicted stats at current command are pred0. This function is optimized only
    over x, not over residual. Window uses 120 s spin-up + W s sample.
    """
    total=120+window_s
    rows=jax_command(x,p,total,command_seed,bases)
    series,ratio,valid=forward(p,x[0],rows,x[25:27],seed,int(120*p.fs),checkpoint)
    pred=metric_vec(metrics(series,1/p.fs,softness))
    corrected=pred+jax.lax.stop_gradient(measured-pred0)
    tgt=jnp.asarray(target(event))
    e_u=jnp.sqrt(jnp.mean(((corrected[:12]-tgt[0])/6)**2))
    e_i=jnp.sqrt(jnp.mean(((corrected[12:24]-tgt[1])/tgt[1])**2))
    e_l=jnp.sqrt(jnp.mean(((corrected[24:]-tgt[2])/tgt[2])**2))
    return (e_u/.05+e_i/.10+e_l/.20)/3


def next_command(x,obs,event,p,hyper):
    """Projected Adam, limited per-round displacement and actual bounds."""
    w=hyper['W'];seed=911;cseed=2001
    bases=signal_bases(p.fs,120+w,cseed)
    current=jnp.asarray(x)
    rows=jax_command(current,p,120+w,cseed,bases)
    series,_,_=forward(p,current[0],rows,current[25:27],seed,int(120*p.fs),True)
    pred0=jax.lax.stop_gradient(metric_vec(metrics(series,1/p.fs,hyper.get('softness',1e-4))))
    measured=jnp.asarray(np.concatenate([obs[n] for n in ('u','Iu','Lux')]))
    scale=jnp.asarray(HI-LO)
    lo=jnp.asarray(LO);hi=jnp.asarray(HI)
    fn=lambda y:objective(lo+scale*y,p,event,measured,pred0,w,seed,cseed,
                          hyper.get('softness',1e-4),True,bases)
    grad=jax.grad(fn)
    y=(current-lo)/scale;start=y;m=jnp.zeros_like(y);v=jnp.zeros_like(y)
    for k in range(1,hyper['steps']+1):
        g=grad(y)
        if not bool(jnp.all(jnp.isfinite(g))):raise FloatingPointError('nonfinite twin gradient')
        m=.9*m+.1*g;v=.999*v+.001*g*g
        y=jnp.clip(y-hyper['lr']*(m/(1-.9**k))/(jnp.sqrt(v/(1-.999**k))+1e-8),0,1)
        y=jnp.clip(y,start-.2,start+.2)
    return np.asarray(lo+scale*y)


def run_sequence_g(plant,event,hyper,seed=1,rounds=25):
    assert 1<=rounds<=25
    rng=np.random.default_rng(seed)
    x=init(event);nominal=nominal_params()
    records=[];best=None;best_error=float('inf');last_valid=x.copy()
    for k in range(rounds):
        duration=SCHEDULE[k];candidate=x.copy()
        obs,e,valid,ratio,series=measure(plant,candidate,event,45.,duration,
            seed=int(rng.integers(1,2**31)),command_seed=int(rng.integers(1,2**31)))
        score=normalized(e)
        if valid and score<best_error:best=candidate.copy();best_error=score
        records.append({'iteration':k+1,'duration_s':duration,
            'time_used_s':sum(r['duration_s']+45 for r in records)+duration+45,
            'e':e.tolist(),'normalized_error':score,'valid':valid,'min_ratio':ratio,
            'command':candidate.tolist(),'warp':None})
        if not valid:
            x=last_valid.copy();continue
        last_valid=candidate.copy()
        if k<rounds-1:
            proposal=next_command(candidate,obs,event,nominal,hyper)
            x=np.clip(proposal,LO,HI)
    return {'method':'G','event':event[0],
        'best_command':None if best is None else best.tolist(),
        'last_command':records[-1]['command'],
        'best_iteration':None if best is None else int(np.argmin([r['normalized_error'] if r['valid'] else np.inf for r in records]))+1,
        'iterations':records,'total_time_s':records[-1]['time_used_s'],
        'valid_rounds':sum(r['valid'] for r in records)}


def official_g(entry,event,seq):
    """Frozen 1800-s, 3-seed official scorer, with measured-round fallback."""
    ranked=sorted((r for r in seq['iterations'] if r['valid']),
                  key=lambda r:(r['normalized_error'],r['iteration']))
    for r in ranked:
        val=official(entry,event,{'method':'G','best_command':r['command'],'best_warp':None})
        if val is not None and val['valid']:return val,r['iteration']
    return official(entry,event,{'method':'G','best_command':init(event).tolist(),'best_warp':None}),None


def candidates():
    return [{'lr':lr,'steps':steps,'W':w} for lr in (.01,.04) for steps in (2,4) for w in (10.,30.,60.)]

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--pilot',action='store_true');args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    entries=members('tuning')
    # Pilot is one object/event at 50 rounds split into two independent sequences;
    # does not qualify as a completed budget-2465-s tuning case.
    if args.pilot:
        entry=entries[0];ev=TUNING[0];h=candidates()[0]
        t=time.perf_counter()
        rows=[run_sequence_g(Plant(Params(**entry['params'])),ev,h,seed=131+entry['index']*7+int(ev[0][-1])+i,
                             rounds=25) for i in range(2)]
        result={'elapsed_wall_s':time.perf_counter()-t,'rounds':sum(len(r['iterations']) for r in rows),
                'cases':len(rows),'hyper':h}
        (out/'pilot.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
    else:
        raise SystemExit('Full tuning requires pilot budget gate and an explicit tuning driver.')
