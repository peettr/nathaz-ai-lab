"""Hot per-window JAX forward/gradient pilot from a saved spin-up state.
One allocated GPU only; report device-wide stats separately from process memory.
"""
import argparse, json, time
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp
from flow_stage1_01h import build

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--state',required=True); p.add_argument('--lag',required=True)
    p.add_argument('--nx',type=int,default=384); p.add_argument('--ny',type=int,default=128)
    p.add_argument('--re',type=float,default=3000); p.add_argument('--collision',default='KBC')
    p.add_argument('--dtype',choices=('float32','float64'),default='float32')
    p.add_argument('--steps',type=int,required=True); p.add_argument('--objective',choices=('mean','var'),required=True)
    p.add_argument('--seed',type=int,default=26022)
    a=p.parse_args(); assert a.steps>0
    assert len(jax.devices())==1 and jax.devices()[0].platform=='gpu'
    state,chunk,nu,control=build(a.nx,a.ny,a.re,a.dtype,a.collision,outlet='fixed_pressure')
    state=(jnp.asarray(np.load(a.state)),jnp.asarray(np.load(a.lag)))
    rng=np.random.default_rng(a.seed)
    alpha=np.exp(-1/256.)
    previous=np.zeros(8)
    white=rng.standard_normal((a.steps,8))
    correlated=np.empty_like(white)
    for i in range(a.steps):
        previous=alpha*previous+np.sqrt(1-alpha*alpha)*white[i]
        correlated[i]=previous
    noise=jnp.asarray(correlated,dtype=control.dtype)
    # Functions are compiled and warmed separately before timing; checkpoint flag
    # changes the reverse-mode scan rematerialization, not the forward equations.
    def objective(x, checkpoint):
        run=jax.checkpoint(chunk) if checkpoint else chunk
        _,u=run(state,noise,x)
        mean=jnp.mean(u,axis=0)
        sigma=jnp.std(u,axis=0)
        return jnp.sum((mean-.023)**2) if a.objective=='mean' else jnp.sum((sigma-.001)**2)
    device=jax.devices()[0]
    for checkpoint in (False,True):
        forward=jax.jit(lambda x:objective(x,checkpoint))
        gradient=jax.jit(jax.grad(lambda x:objective(x,checkpoint)))
        forward(control).block_until_ready()
        gradient(control).block_until_ready()
        before=device.memory_stats() or {}
        t=time.perf_counter(); val=forward(control).block_until_ready(); fw=time.perf_counter()-t
        t=time.perf_counter(); grad=gradient(control).block_until_ready(); gw=time.perf_counter()-t
        after=device.memory_stats() or {}
        print(json.dumps({'stage':'hot_pilot','objective':a.objective,'checkpoint':checkpoint,
                          'dtype':a.dtype,'steps':a.steps,'forward_s':fw,'forward_s_per_step':fw/a.steps,
                          'gradient_s':gw,'ratio':gw/fw,'value':float(val),
                          'gradient_norm':float(jnp.linalg.norm(grad)),
                          'memory_stats_before':before,'memory_stats_after':after,
                          'memory_note':'JAX device allocator counters may be cumulative; no reset inferred'},default=str),flush=True)
if __name__=='__main__':main()
