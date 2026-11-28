"""L26.22-01o: extra FP64 FD batches and detached-start segment AD.
Read-only inputs: BGK qualified state and frozen 01m per-point JSONL.
Run only on an allocated A10; save append-only per-point evidence in run_01o.
"""
import argparse
import json
import math
import time
from pathlib import Path
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp
import armA_case_01d  # import-only optional-backend shim, never executes Warp
from checkpoint_pilot_01i import correlated_noise
from stage2_01m import (ROOT, STATE, SEEDS, WIDTHS, TM, TV, BLOCK, ALL_T,
                        WINDOWS, beginning, fd_prefixes, objective, compare, safe, emit)

RUN = ROOT / 'run_01o'
OLD = ROOT / 'run_01m/stage2'
SEGMENTS = {'mean': TM // 2, 'var': TV // 8}

def old_records(idx):
    rows = [json.loads(s) for s in (OLD / f'point_{idx}.jsonl').read_text().splitlines()]
    if sum(r.get('type') == 'complete' for r in rows) != 1:
        raise RuntimeError('Original point not complete')
    found = {}
    for r in rows:
        if r.get('type') == 'result' and r['dtype'] == 'float64':
            key = (r['metric'], r['T'], r['fd_step_fraction'])
            if key in found: raise ValueError('duplicate original key')
            found[key] = r
    for kind in ('mean', 'var'):
        for T in WINDOWS[kind]:
            if (kind, T, .01) not in found: raise ValueError(('missing original', kind, T))
    return found

def fd_batches(idx, st, chunk, cmd, noise, old, out):
    base = np.asarray(cmd)
    steps = (.005, .0025, .001) if idx >= 2 else (.0025, .001)
    for fraction in steps:
        perturb = fraction * WIDTHS * np.eye(18)
        inputs = jnp.asarray(np.concatenate((base + perturb, base - perturb)), dtype=cmd.dtype)
        tick = time.perf_counter()
        vals = np.asarray(fd_prefixes(st, chunk, noise, inputs).block_until_ready())
        seconds = time.perf_counter() - tick
        if vals.shape != (36, len(ALL_T), 2) or not np.isfinite(vals).all():
            raise RuntimeError('Nonfinite/shape-invalid FD batch')
        emit(out, {'type':'fd_batch','point':idx,'step':fraction,'seconds_including_jit':seconds})
        for kind, col in (('mean', 0), ('var', 1)):
            Ts = WINDOWS[kind] if fraction == .005 else (TM if kind == 'mean' else TV,)
            for T in Ts:
                j = ALL_T.index(T)
                fd = (vals[:18,j,col] - vals[18:,j,col]) / (2*fraction*WIDTHS)
                prior = old[(kind,T,.01)]
                ad = np.asarray(prior['ad'], dtype=float)
                one = np.asarray(prior['fd'], dtype=float)
                emit(out, {'type':'fd_result','point':idx,'seed':SEEDS[idx],
                           'metric':kind,'T':T,'fd_step_fraction':fraction,
                           'fd':fd.tolist(),'ad':ad.tolist(),
                           'vs_ad':compare(ad,fd),
                           'vs_1pct_relative':float(np.linalg.norm(fd-one)/np.linalg.norm(one)),
                           'fd_unreliable':bool(np.linalg.norm(fd-one)/np.linalg.norm(one)>.05)
                           if fraction == .005 else None})

def segment_gradients(idx, st, chunk, cmd, noise, old, out):
    # Segment target = sum_z (within-segment mean_z-.023)^2 or
    # sum_z (within-segment sigma_z-.001)^2. Each segment starts at the
    # SAME trajectory's state at its boundary, held constant for AD;
    # its own segment noise is the matching slice of the full trace.
    for kind, seg in SEGMENTS.items():
        T = TM if kind == 'mean' else TV
        count = T//seg
        if T % seg or seg % BLOCK: raise ValueError('segment layout')
        state = st
        grads = []
        for i in range(count):
            z = noise[i*seg:(i+1)*seg]
            fun = jax.jit(jax.grad(lambda x: objective(state,chunk,z,x,seg,kind)))
            tick = time.perf_counter()
            g = np.asarray(fun(cmd).block_until_ready())
            seconds = time.perf_counter()-tick
            if g.shape != (18,): raise ValueError('gradient shape')
            grads.append(g)
            emit(out, {'type':'segment','point':idx,'metric':kind,'segment_index':i,
                       'start_step':i*seg,'end_step':(i+1)*seg,'segment_T':seg,
                       'gradient':g.tolist(),'finite':bool(np.isfinite(g).all()),
                       'seconds_including_jit':seconds})
            # No change to command, state or noise: carry state along same full trajectory.
            @jax.jit
            def advance(s, zs):
                return jax.lax.scan(lambda carry, block: (chunk(carry,block,cmd)[0],None),
                                    s,zs.reshape(seg//BLOCK,BLOCK,8))[0]
            state = advance(state,z)
            state[0].block_until_ready()
        average = np.mean(np.asarray(grads),axis=0)
        ref = np.asarray(old[(kind,T,.01)]['fd'],dtype=float)
        emit(out, {'type':'segment_average','point':idx,'metric':kind,'T':T,
                   'segment_T':seg,'segment_count':count,
                   'gradient':average.tolist(),'against_1pct':compare(average,ref),
                   'definition':'mean of AD of separate segment statistic, each segment start state detached; not full-chain AD'})

def main():
    p=argparse.ArgumentParser();p.add_argument('--point',type=int,required=True); a=p.parse_args()
    idx=a.point
    if idx not in range(5): raise ValueError(idx)
    if len(jax.devices()) != 1 or jax.devices()[0].platform != 'gpu':
        raise RuntimeError('one allocated GPU required')
    old=old_records(idx)
    st,chunk,cmd=beginning('float64')
    noise=correlated_noise(TV,SEEDS[idx],cmd.dtype)
    RUN.mkdir(parents=True,exist_ok=True)
    out=RUN/f'point_{idx}.jsonl'
    if out.exists(): raise FileExistsError(out)
    emit(out, {'type':'start','point':idx,'seed':SEEDS[idx],
               'source':'01m BGK qualified state; original 01m point JSONL',
               'segment_definition':'independent segment statistic on same full trajectory; start state detached'})
    fd_batches(idx,st,chunk,cmd,noise,old,out)
    segment_gradients(idx,st,chunk,cmd,noise,old,out)
    emit(out, {'type':'complete','point':idx})
if __name__ == '__main__': main()
