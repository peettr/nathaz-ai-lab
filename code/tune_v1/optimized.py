"""Reuse one JIT graph per W across objects, events and measurement seeds.

Original method_g, source inputs and official scoring remain unchanged. The first
call to each W compiles; subsequent calls only supply dynamic commands and
observations. Never reads scoring members.
"""
from functools import lru_cache
import numpy as np
import jax
import jax.numpy as jnp
import method_g as base
from twin_jax import forward, metrics

@lru_cache(None)
def kernels(window_s, softness):
    p=base.nominal_params()
    w=float(window_s)
    bases=base.signal_bases(p.fs,120+w,2001)
    lo=jnp.asarray(base.LO);hi=jnp.asarray(base.HI);scale=hi-lo
    def prediction(x):
        rows=base.jax_command(x,p,120+w,2001,bases)
        series,_,_=forward(p,x[0],rows,x[25:27],911,int(120*p.fs),True)
        return base.metric_vec(metrics(series,1/p.fs,softness))
    predict=jax.jit(prediction)
    def loss(y,measured,pred0,tgt):
        x=lo+scale*y
        pred=prediction(x)
        corrected=pred+jax.lax.stop_gradient(measured-pred0)
        eu=jnp.sqrt(jnp.mean(((corrected[:12]-tgt[0])/6)**2))
        ei=jnp.sqrt(jnp.mean(((corrected[12:24]-tgt[1])/tgt[1])**2))
        el=jnp.sqrt(jnp.mean(((corrected[24:]-tgt[2])/tgt[2])**2))
        return (eu/.05+ei/.10+el/.20)/3
    grad=jax.jit(jax.grad(loss))
    return predict,grad,lo,hi,scale

def next_command(x,obs,event,p,hyper):
    predict,grad,lo,hi,scale=kernels(hyper['W'],hyper.get('softness',1e-4))
    current=jnp.asarray(x)
    pred0=jax.lax.stop_gradient(predict(current))
    measured=jnp.asarray(np.concatenate([obs[n] for n in ('u','Iu','Lux')]))
    tgt=jnp.asarray(base.target(event))
    y=(current-lo)/scale;start=y;m=jnp.zeros_like(y);v=jnp.zeros_like(y)
    for k in range(1,hyper['steps']+1):
        g=grad(y,measured,pred0,tgt)
        if not bool(jnp.all(jnp.isfinite(g))):raise FloatingPointError('nonfinite twin gradient')
        m=.9*m+.1*g;v=.999*v+.001*g*g
        y=jnp.clip(y-hyper['lr']*(m/(1-.9**k))/(jnp.sqrt(v/(1-.999**k))+1e-8),0,1)
        y=jnp.clip(y,start-.2,start+.2)
    return np.asarray(lo+scale*y)

def activate():
    base.next_command=next_command
