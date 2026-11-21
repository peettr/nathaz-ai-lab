"""L26.22 arm A. Execute ONLY on an allocated CRC GPU.
XLB v0.3.1 supplies D2Q9, BGK collision, quadratic equilibrium,
macroscopic moments and streaming. Warp/plot dependencies are import-only
and deliberately fail closed if any of their APIs is invoked.
"""
import argparse
import json
import sys
import time
import types
import subprocess
import threading

# XLB 0.3.1 imports its optional backends eagerly, including on JAX-only runs.
class DisabledWarpSymbol:
    def __class_getitem__(cls, item):
        return cls
    def __call__(self, *args, **kwargs):
        # XLB evaluates Warp annotation expressions while importing JAX paths.
        # This is metadata only; execution of any Warp kernel remains disabled.
        return self

class DisabledBackend(types.ModuleType):
    def __getattr__(self, name):
        if name in ("kernel", "func"):
            return lambda fn: fn
        if name in ("vec3i", "vec2i", "vec3", "vec3f", "vec", "mat33f", "mat33", "mat", "array", "array1d", "array2d", "array3d", "array4d",
                    "float16", "float32", "float64", "int32", "uint8", "uint64", "bool"):
            return DisabledWarpSymbol()
        raise RuntimeError("Forbidden optional backend invoked: " + self.__name__ + "." + name)

for optional in ("warp", "pyvista", "trimesh", "stl", "matplotlib"):
    if optional not in sys.modules:
        disabled = DisabledBackend(optional)
        disabled.__path__ = []  # optional package may be imported with a submodule
        sys.modules[optional] = disabled
sys.modules["matplotlib.pylab"] = DisabledBackend("matplotlib.pylab")
sys.modules["matplotlib"].pylab = sys.modules["matplotlib.pylab"]
sys.modules["matplotlib.cm"] = DisabledBackend("matplotlib.cm")
sys.modules["matplotlib"].cm = sys.modules["matplotlib.cm"]
sys.modules["warp.utils"] = DisabledBackend("warp.utils")
sys.modules["warp.utils"].__path__ = []
sys.modules["warp"].utils = sys.modules["warp.utils"]
sys.modules["warp.utils"].ScopedTimer = type("DisabledScopedTimer", (), {})

import numpy as np
import jax
import jax.numpy as jnp
import xlb
from xlb.compute_backend import ComputeBackend
from xlb.precision_policy import PrecisionPolicy
from xlb.velocity_set import D2Q9
from xlb.operator.collision import BGK
from xlb.operator.stream import Stream
from xlb.operator.equilibrium import QuadraticEquilibrium
from xlb.operator.macroscopic import Macroscopic


def make_model(nx, ny, steps, seed=26022):
    assert ny % 8 == 0 and nx >= 32 and steps >= 4
    backend = ComputeBackend.JAX
    precision = PrecisionPolicy.FP32FP32
    velocity_set = D2Q9(precision_policy=precision, compute_backend=backend)
    xlb.init(velocity_set=velocity_set, default_backend=backend,
             default_precision_policy=precision)
    eq = QuadraticEquilibrium(velocity_set, precision, backend)
    bgk = BGK(velocity_set, precision, backend)
    stream = Stream(velocity_set, precision, backend)
    moments = Macroscopic(velocity_set, precision, backend)
    noise = jnp.asarray(np.random.default_rng(seed).standard_normal((steps, 8)), dtype=jnp.float32)
    band = jnp.minimum(7, jnp.arange(ny) * 8 // ny)
    ys = jnp.asarray(np.linspace(3, ny - 4, 12, dtype=np.int32))
    xx = jnp.arange(nx)[:, None]
    yy = jnp.arange(ny)[None, :]
    rough = sum(jnp.exp(-((xx-x)/4.0)**2) * jnp.exp(-((yy-y)/3.0)**2)
                for x, y in ((nx//3, ny//4), (nx//3+6, ny//4),
                             (nx//3+12, ny//4), (nx//3, 3*ny//4),
                             (nx//3+6, 3*ny//4), (nx//3+12, 3*ny//4)))
    region = jnp.where(yy < ny//2, 0, 1)
    rho0 = jnp.ones((1, nx, ny), dtype=jnp.float32)
    u0 = jnp.zeros((2, nx, ny), dtype=jnp.float32).at[0].set(.025)
    f0 = eq(rho0, u0)
    omega = jnp.float32(1.0 / (3.0 * .02 + .5))
    def step(carry, t):
        f, lag, command = carry
        lag = lag + (command[:8] - lag) / 5.0
        speed = jnp.clip(lag + command[8:16]*noise[t], .003, .09)[band]
        rho, velocity = moments(f)
        # dynamic argument, no BC object holding/tracing the command
        inlet_u = jnp.stack((speed, jnp.zeros_like(speed)), axis=0)[:, None, :]
        feq_inlet = eq(rho[:, :1, :], inlet_u)
        f = f.at[:, :1, :].set(feq_inlet)
        rho, velocity = moments(f)
        feq = eq(rho, velocity)
        post = bgk(f, feq, rho, velocity, omega)
        # Smooth drag replaces discontinuous obstacle heights. Two independently
        # tunable coefficients act on three roughness elements in each half.
        drag = jnp.clip(command[16:18], 0., .2)[region] * rough
        slowed = velocity.at[0].set(velocity[0] * (1.0-drag))
        post = post + eq(rho, slowed) - feq
        moved = stream(post)
        # horizontal no-slip: full-way bounce-back at upper/lower rows;
        # outlet: copy previous column (first-order zero normal derivative).
        opposite = jnp.asarray(velocity_set.opp_indices)
        moved = moved.at[:, :, 0].set(moved[opposite, :, 0])
        moved = moved.at[:, :, -1].set(moved[opposite, :, -1])
        moved = moved.at[:, -1, :].set(moved[:, -2, :])
        moved = moved.at[:, :1, :].set(feq_inlet)
        _, vel = moments(moved)
        return (moved, lag, command), vel[0, nx-8, ys]
    def samples(command, checkpoint=False):
        lag = jnp.full((8,), .025, dtype=jnp.float32)
        fn = jax.checkpoint(step) if checkpoint else step
        _, u = jax.lax.scan(fn, (f0, lag, command), jnp.arange(steps))
        return u
    def objectives(command, checkpoint=False):
        u = samples(command, checkpoint)
        return jnp.stack((jnp.square(jnp.mean(u,axis=0)-.023).sum(),
                          jnp.square(jnp.std(u,axis=0)-.001).sum()))
    return samples, objectives


def initial_command():
    return np.r_[np.full(8,.025), np.full(8,.002), [.025,.04]].astype('float32')


def metrics(ad, fd):
    den = np.linalg.norm(fd)
    return {'cosine': float(np.dot(ad,fd)/(np.linalg.norm(ad)*den)) if den and np.linalg.norm(ad) else None,
            'relative_difference': float(np.linalg.norm(ad-fd)/den) if den else None,
            'ad_norm':float(np.linalg.norm(ad)), 'fd_norm':float(den)}


def gpu_memory_peak(fn):
    """Sample allocated-device nvidia-smi used memory; whole-device, not JAX-only."""
    stop = threading.Event()
    readings = []
    def sample():
        while not stop.is_set():
            p = subprocess.run(['nvidia-smi','-i',__import__('os').environ['CUDA_VISIBLE_DEVICES'],
                                '--query-gpu=memory.used','--format=csv,noheader,nounits'], capture_output=True, text=True)
            if p.returncode == 0:
                readings.extend(int(v.strip()) for v in p.stdout.splitlines() if v.strip().isdigit())
            stop.wait(.05)
    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    try:
        t = time.perf_counter()
        value = fn()
        wall = time.perf_counter()-t
    finally:
        stop.set(); thread.join(timeout=3)
    return value, wall, max(readings) if readings else None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--nx',type=int,default=64)
    parser.add_argument('--ny',type=int,default=32)
    parser.add_argument('--steps',type=int,default=16)
    parser.add_argument('--seed',type=int,default=26022)
    parser.add_argument('--mode',choices=('smoke','timing','window'),default='smoke')
    args=parser.parse_args()
    devices=jax.devices()
    assert len(devices)==1 and devices[0].platform=='gpu', 'fail closed: one allocated GPU required'
    print(json.dumps({'stage':'device','devices':[str(d) for d in devices],
                      'jax':jax.__version__,'xlb':getattr(xlb,'__version__','0.3.1')}),flush=True)
    samples, objectives = make_model(args.nx,args.ny,args.steps,args.seed)
    c=jnp.asarray(initial_command()); target=0
    fn=jax.jit(lambda x:objectives(x)[target])
    val=fn(c).block_until_ready()  # compile excluded from warm-step throughput
    t=time.perf_counter(); val=fn(c).block_until_ready(); forward=time.perf_counter()-t
    print(json.dumps({'stage':'forward','steps':args.steps,'warm_seconds':forward,
                      'seconds_per_step':forward/args.steps,'value':float(val)}),flush=True)
    if args.mode=='window':
        u=np.asarray(jax.jit(samples)(c)); batch=8
        summaries=[]
        for n in range(batch*2,args.steps+1,batch):
            parts=u[:n].reshape(n//batch,batch,12)
            means=parts.mean(axis=1)
            stds=parts.std(axis=1,ddof=1)
            se_mean=means.std(axis=0,ddof=1)/np.sqrt(len(parts))/.023
            se_var=stds.std(axis=0,ddof=1)/np.sqrt(len(parts))
            ref=np.maximum(u[:n].std(axis=0,ddof=1),1e-10)
            summaries.append({'steps':n,'max_mean_error':float(np.max(se_mean)),
                              'max_std_error':float(np.max(se_var/ref))})
        print(json.dumps({'stage':'window','batch_steps':batch,'rows':summaries,
                          'T_m':next((r['steps'] for r in summaries if r['max_mean_error']<=.02),None),
                          'T_v':next((r['steps'] for r in summaries if r['max_std_error']<=.05),None)}),flush=True)
        return
    for ckpt in (False,True) if args.mode=='timing' else (False,):
        gfn=jax.jit(jax.grad(lambda x:objectives(x,ckpt)[target]))
        grad,wall,peak=gpu_memory_peak(lambda:np.asarray(gfn(c)))
        print(json.dumps({'stage':'gradient','checkpoint':ckpt,'seconds_with_compile':wall,
                          'peak_gpu_mib_whole_device':peak,'grad':grad.tolist()}),flush=True)
        if args.mode=='smoke' and not ckpt:
            scale=np.r_[np.full(8,.06),np.full(8,.01),[.2,.2]].astype('float32')
            for fraction in (.01,.005):
                delta=scale*fraction
                fd=np.zeros(18,dtype='float32')
                for k in range(18):
                    cp=np.asarray(c).copy(); cm=cp.copy(); cp[k]+=delta[k]; cm[k]-=delta[k]
                    fd[k]=(float(fn(jnp.asarray(cp)))-float(fn(jnp.asarray(cm))))/(2*delta[k])
                print(json.dumps({'stage':'smoke','fraction':fraction,'ad':grad.tolist(),
                                  'fd':fd.tolist(),**metrics(grad,fd)}),flush=True)

if __name__=='__main__':main()
