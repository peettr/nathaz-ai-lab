"""L26.22-01e stage 1: bounded forward qualification on allocated A10 only.
Uses reviewed XLB JAX collision/stream and the 01d import shim. No score decision
is made unless both the fluctuation and spin-up gates are actually observed.
"""
import os
os.environ.setdefault('XLA_PYTHON_CLIENT_PREALLOCATE', 'false')
import sys, json, time, argparse
from pathlib import Path
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp
# Import shim and original instruction definition; no execution of disabled backend.
import armA_case_01d as old
from xlb.compute_backend import ComputeBackend
from xlb.precision_policy import PrecisionPolicy
from xlb.velocity_set import D2Q9
from xlb.operator.collision import BGK
from xlb.operator.stream import Stream
from xlb.operator.equilibrium import QuadraticEquilibrium
from xlb.operator.macroscopic import Macroscopic
import xlb
try:
    from xlb.operator.collision.kbc import KBC
except ImportError:
    KBC = None

def emit(**fields):
    print(json.dumps(fields, allow_nan=False), flush=True)

def build(nx, ny, re, dtype, collision):
    precision = PrecisionPolicy.FP64FP64 if dtype == 'float64' else PrecisionPolicy.FP32FP32
    scalar = jnp.float64 if dtype == 'float64' else jnp.float32
    vs = D2Q9(precision_policy=precision, compute_backend=ComputeBackend.JAX)
    xlb.init(velocity_set=vs, default_backend=ComputeBackend.JAX, default_precision_policy=precision)
    eq = QuadraticEquilibrium(vs, precision, ComputeBackend.JAX)
    col = (KBC if collision == 'KBC' else BGK)(vs, precision, ComputeBackend.JAX)
    stream = Stream(vs, precision, ComputeBackend.JAX)
    moments = Macroscopic(vs, precision, ComputeBackend.JAX)
    uin = .05
    nu = uin * (ny - 2) / re
    omega = scalar(1 / (3 * nu + .5))
    ys = jnp.asarray(np.linspace(3, ny - 4, 12, dtype=np.int32))
    band = jnp.minimum(7, jnp.arange(ny) * 8 // ny)
    xx, yy = jnp.arange(nx)[:, None], jnp.arange(ny)[None, :]
    rough = sum(jnp.exp(-((xx-x)/4.)**2)*jnp.exp(-((yy-y)/3.)**2)
                for x,y in ((nx//3,ny//4),(nx//3+6,ny//4),(nx//3+12,ny//4),
                            (nx//3,3*ny//4),(nx//3+6,3*ny//4),(nx//3+12,3*ny//4)))
    region = jnp.where(yy < ny//2, 0, 1)
    rho0 = jnp.ones((1,nx,ny), dtype=scalar)
    u0 = jnp.zeros((2,nx,ny), dtype=scalar).at[0].set(uin)
    state = (eq(rho0,u0), jnp.full((8,),uin,dtype=scalar))
    opposite = jnp.asarray(vs.opp_indices)
    command = jnp.asarray(np.r_[np.full(8,uin),np.full(8,.006),[.025,.04]],dtype=scalar)
    # Counter-indexed noise permits restart and exactly paired gradient runs.
    def timestep(carry, t):
        f,lag,command = carry
        lag = lag + (command[:8]-lag)/5.
        # Seed is fixed in caller; noise is a dynamic vector per timestep.
        noise = t[1]; idx=t[0]
        speed = jnp.clip(lag+command[8:16]*noise, .003,.09)[band]
        rho, velocity = moments(f)
        inlet_u = jnp.stack((speed,jnp.zeros_like(speed)),axis=0)[:,None,:]
        inlet = eq(rho[:,:1,:],inlet_u)
        f = f.at[:,:1,:].set(inlet)
        rho, velocity = moments(f)
        feq = eq(rho,velocity)
        post = col(f,feq,rho,velocity,omega)
        drag = jnp.clip(command[16:18],0.,.2)[region]*rough
        slowed = velocity.at[0].set(velocity[0]*(1.-drag))
        post = post + eq(rho,slowed)-feq
        moved = stream(post)
        moved = moved.at[:,:,0].set(moved[opposite,:,0])
        moved = moved.at[:,:,-1].set(moved[opposite,:,-1])
        moved = moved.at[:,-1,:].set(moved[:,-2,:])
        moved = moved.at[:,:1,:].set(inlet)
        _,v = moments(moved)
        samples = v[0,nx-8,ys]
        return (moved,lag,command), samples
    @jax.jit
    def chunk(state, noise, control):
        final, samples = jax.lax.scan(timestep,(*state,control),(jnp.arange(noise.shape[0]),noise))
        return final[:2], samples
    return state,chunk,nu,command

def spectrum_fraction(x):
    a=np.asarray(x,dtype=float); a=a-np.mean(a)
    p=np.abs(np.fft.rfft(a))**2
    p[0]=0
    return float(p.max()/p.sum()) if p.sum()>0 else None

def gate(series, transit, target=.05):
    if len(series)<2*transit: return {'qualified':False,'reason':'less_than_two_transits'}
    before=series[-2*transit:-transit]
    after=series[-transit:]
    means=np.mean(after,axis=0)
    mean_diff=np.abs(means-np.mean(before,axis=0))/np.maximum(np.abs(means),1e-8)
    ratios=np.std(after,axis=0,ddof=1)/np.maximum(np.abs(means),1e-8)
    peaks=[spectrum_fraction(after[:,k]) for k in range(12)]
    pulsing=sum(r>=target and p is not None and p<.5 for r,p in zip(ratios,peaks))
    return {'qualified':bool(np.all(mean_diff<=.02) and pulsing>=6),
            'spinup_pass':bool(np.all(mean_diff<=.02)),'pulse_pass':pulsing>=6,
            'max_mean_relative_change':float(max(mean_diff)),
            'mean_relative_changes':mean_diff.tolist(),
            'fluctuation_ratios':ratios.tolist(), 'peak_power_fraction':peaks,
            'pulse_count':pulsing}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--nx',type=int,default=192); ap.add_argument('--ny',type=int,default=128)
    ap.add_argument('--re',type=float,default=1500.); ap.add_argument('--chunk',type=int,default=512)
    ap.add_argument('--max-steps',type=int,default=24576)
    ap.add_argument('--dtype',choices=('float32','float64'),default='float32')
    ap.add_argument('--collision',choices=('KBC','BGK'),default='KBC')
    ap.add_argument('--seed',type=int,default=26022)
    ap.add_argument('--out',required=True)
    args=ap.parse_args()
    assert args.ny>=128 and args.ny%8==0 and args.nx>=32 and args.chunk>0
    assert len(jax.devices())==1 and jax.devices()[0].platform=='gpu'
    out=Path(args.out); out.mkdir(parents=True,exist_ok=False)
    state,run,nu,command=build(args.nx,args.ny,args.re,args.dtype,args.collision)
    transit=int(np.ceil(args.nx/.05))
    emit(stage='config',nx=args.nx,ny=args.ny,re=args.re,nu=nu,collision=args.collision,
         dtype=args.dtype,transit=transit,seed=args.seed,device=str(jax.devices()[0]))
    rng=np.random.default_rng(args.seed)
    history=[]; start=time.perf_counter(); qualified=False; spinup_stop=None
    measured_steps=0; measured_seconds=0.
    for stop in range(args.chunk,args.max_steps+1,args.chunk):
        noise=jnp.asarray(rng.standard_normal((args.chunk,8)),dtype=command.dtype)
        tick=time.perf_counter()
        state, samples=run(state,noise,command)
        block=np.asarray(samples.block_until_ready())
        measured_seconds+=time.perf_counter()-tick
        measured_steps+=args.chunk
        if not np.isfinite(block).all() or not np.isfinite(np.asarray(state[0][...,::16,::16])).all():
            emit(stage='unstable',steps=stop); break
        history.append(block)
        if stop>=2*transit and stop%max(args.chunk,(transit//args.chunk)*args.chunk)==0:
            stats=gate(np.concatenate(history),transit)
            emit(stage='gate',steps=stop,**stats)
            if stats['qualified']:
                qualified=True
                spinup_stop=stop
                np.save(out/f'state_{args.dtype}.npy',np.asarray(state[0]))
                np.save(out/f'lag_{args.dtype}.npy',np.asarray(state[1]))
                emit(stage='spinup_saved',steps=stop)
                break
    emit(stage='final',steps=stop,elapsed_seconds=time.perf_counter()-start,
         measured_forward_s_per_step=measured_seconds/measured_steps,qualified=qualified)
    if not qualified: raise SystemExit(42)
    # Only post-spin-up samples enter statistical windows; no transient first crossing.
    post=[]
    count=0
    while count < 4*transit:
        noise=jnp.asarray(rng.standard_normal((args.chunk,8)),dtype=command.dtype)
        state, samples=run(state,noise,command)
        post.append(np.asarray(samples.block_until_ready()))
        count+=args.chunk
    np.save(out/f'post_probe_{args.dtype}.npy',np.concatenate(post))
    emit(stage='postspinup',steps=count,elapsed_seconds=time.perf_counter()-start)
if __name__=='__main__':main()
