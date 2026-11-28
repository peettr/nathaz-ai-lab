"""01k component ablation: paired 840-step FP64 AD/FD, allocated GPU only.
Original spin-up state, one fixed instruction, common noise and perturbation range.
The eight 2^3 combinations isolate collision, outlet, and colored noise.
"""
import argparse, itertools, json, math, time
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp
from flow_stage1_01h import build
from checkpoint_pilot_01i import correlated_noise


def finite_json(x):
    if isinstance(x, dict):
        return {k: finite_json(v) for k, v in x.items()}
    if isinstance(x, (tuple, list)):
        return [finite_json(v) for v in x]
    if isinstance(x, np.ndarray):
        return finite_json(x.tolist())
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.floating, float)):
        return float(x) if math.isfinite(float(x)) else str(float(x))
    if isinstance(x, (np.integer, int)):
        return int(x)
    return x


def emit(**kw):
    print(json.dumps(finite_json(kw), allow_nan=False), flush=True)


def metrics(ad, fd):
    af, ff = np.isfinite(ad).all(), np.isfinite(fd).all()
    an, fn = np.linalg.norm(ad), np.linalg.norm(fd)
    cos = float(np.dot(ad, fd)/(an*fn)) if af and ff and an and fn and np.isfinite(an*fn) else None
    rel = float(np.linalg.norm(ad-fd)/fn) if af and ff and fn and np.isfinite(fn) else None
    return dict(finite_ad=bool(af), finite_fd=bool(ff), ad_norm=an,
                fd_norm=fn, cosine=cos, relative_difference=rel,
                ad_nan=int(np.isnan(ad).sum()), ad_inf=int(np.isinf(ad).sum()))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--state', required=True); p.add_argument('--lag', required=True)
    p.add_argument('--seconds', type=float, default=3000)
    args=p.parse_args()
    assert len(jax.devices()) == 1 and jax.devices()[0].platform == 'gpu', jax.devices()
    # First, convert the same FP32 terminal state to FP64 and warm one transit
    # in the original KBC + fixed-pressure configuration, independent of ablation.
    _, base_chunk, _, base_cmd = build(384,128,3000,'float64','KBC',outlet='fixed_pressure')
    state=(jnp.asarray(np.load(args.state),dtype=jnp.float64),
           jnp.asarray(np.load(args.lag),dtype=jnp.float64))
    warm=correlated_noise(8192,26023,jnp.float64)
    for i in range(0,8192,512):
        state,_=base_chunk(state,warm[i:i+512],base_cmd)
    state[0].block_until_ready()
    base_noise=correlated_noise(840,26024,jnp.float64).reshape(21,40,8)
    command=np.asarray(base_cmd,dtype=np.float64)
    emit(stage='config',gpu=str(jax.devices()[0]),warm_steps=8192,steps=840,
         noise_seed=26024,precision='float64',fd_fraction=.01,command=command,
         variants='full 2x2x2; same warmed KBC/fixed-pressure start state')
    start=time.monotonic()
    for collision,outlet,noise_on in itertools.product(('KBC','BGK'),('fixed_pressure','zero_gradient'),(True,False)):
        if time.monotonic()-start > args.seconds:
            emit(stage='budget_stop',elapsed_s=time.monotonic()-start)
            break
        _,chunk,_,cmd=build(384,128,3000,'float64',collision,outlet=outlet)
        chunks=base_noise if noise_on else jnp.zeros_like(base_noise)
        def value(x):
            def one(carry,z):
                flow,total=carry
                flow,samples=jax.checkpoint(chunk)(flow,z,x)
                return (flow,total+jnp.sum(samples,axis=0)),None
            (_,total),_=jax.lax.scan(one,(state,jnp.zeros((12,),dtype=jnp.float64)),chunks)
            return jnp.sum((total/840-.023)**2)
        f=jax.jit(value); grad=jax.jit(jax.grad(value))
        label=dict(collision=collision,outlet=outlet,colored_noise=noise_on)
        try:
            g=np.asarray(grad(jnp.asarray(command)),dtype=np.float64)
            ad_value=float(f(jnp.asarray(command)))
            fd=[]
            for i in range(18):
                width=.087 if i<8 else (.02 if i<16 else .2)
                h=.01*width
                plus=command.copy(); minus=command.copy()
                plus[i]+=h; minus[i]-=h
                fd.append((float(f(jnp.asarray(plus)))-float(f(jnp.asarray(minus))))/(2*h))
            fd=np.asarray(fd)
            emit(stage='ablation',**label,value=ad_value,**metrics(g,fd),
                 ad=g,fd=fd,elapsed_s=time.monotonic()-start)
        except Exception as exc:
            emit(stage='ablation_error',**label,error=repr(exc),elapsed_s=time.monotonic()-start)
        del f,grad
        jax.clear_caches()
    emit(stage='done',elapsed_s=time.monotonic()-start)

if __name__=='__main__': main()
