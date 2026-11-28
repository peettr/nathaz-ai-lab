"""L26.22-01i: bounded nested-scan checkpoint gradient from 01h state.
GPU allocation only. One objective/precision per process; no full time-history retention.
"""
import argparse, json, math, time
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp
from flow_stage1_01h import build


def correlated_noise(n, seed, dtype, initial=None):
    rng = np.random.default_rng(seed)
    alpha = math.exp(-1.0 / 256.0)
    previous = np.zeros(8) if initial is None else initial.copy()
    noise = np.empty((n, 8), dtype=np.float64)
    for i in range(n):
        previous = alpha * previous + math.sqrt(1 - alpha * alpha) * rng.standard_normal(8)
        noise[i] = previous
    return jnp.asarray(noise, dtype=dtype)


def pilot(args):
    devices = jax.devices()
    assert len(devices) == 1 and devices[0].platform == 'gpu', devices
    init, chunk, _, command = build(384, 128, 3000, args.dtype, 'KBC', outlet='fixed_pressure')
    state = (jnp.asarray(np.load(args.state), dtype=command.dtype),
             jnp.asarray(np.load(args.lag), dtype=command.dtype))
    device = devices[0]
    # Distinct deterministic post-state noise for all AD/FD evaluations.
    # FP64 spin-up is separately executed after conversion (>= one 7680-step transit).
    if args.dtype == 'float64':
        n_warm = 8192
        warm = correlated_noise(n_warm, 26023, command.dtype)
        for start in range(0, n_warm, 512):
            state, _ = chunk(state, warm[start:start + 512], command)
        jax.block_until_ready(state[0])
        print(json.dumps({'stage':'fp64_precision_warm','steps':n_warm,'transit_min':7680}), flush=True)
    k = args.block
    assert args.steps % k == 0, (args.steps, k)
    noise = correlated_noise(args.steps, 26024, command.dtype).reshape(args.steps // k, k, 8)
    # Rematerialize each inner scan in reverse mode; outer scan stores only block states.
    block = jax.checkpoint(chunk)
    def objective(x):
        def outer(carry, series):
            state, s1, s2 = carry
            state, samples = block(state, series, x)
            s1 = s1 + jnp.sum(samples, axis=0)
            s2 = s2 + jnp.sum(samples * samples, axis=0)
            return (state, s1, s2), None
        zero = jnp.zeros(12, command.dtype)
        (_, total, square), _ = jax.lax.scan(outer, (state, zero, zero), noise)
        mu = total / args.steps
        sigma = jnp.sqrt(jnp.maximum(square / args.steps - mu * mu, 1e-20))
        if args.objective == 'mean':
            return jnp.sum((mu - .023) ** 2)
        return jnp.sum((sigma - .001) ** 2)
    forward = jax.jit(objective)
    gradient = jax.jit(jax.grad(objective))
    # Compile/warm separately; failed compilation is NOT a hot timing.
    print(json.dumps({'stage':'compile_start','dtype':args.dtype,'objective':args.objective,
                      'steps':args.steps,'block':k,'blocks':args.steps//k}), flush=True)
    forward(command).block_until_ready()
    gradient(command).block_until_ready()
    before = device.memory_stats() or {}
    t = time.perf_counter(); value = forward(command).block_until_ready(); fw = time.perf_counter()-t
    t = time.perf_counter(); grad = gradient(command).block_until_ready(); gw = time.perf_counter()-t
    after = device.memory_stats() or {}
    print(json.dumps({'stage':'hot_pilot','dtype':args.dtype,'objective':args.objective,
                      'steps':args.steps,'block':k,'forward_s':fw,'gradient_s':gw,
                      'gradient_to_forward':gw/fw,'gradient_norm':float(jnp.linalg.norm(grad)),
                      'value':float(value),'device_memory_before':before,
                      'device_memory_after':after,'gpu':str(device),
                      'peak_note':'allocator peak is cumulative in this process; check peak_bytes_in_use vs pre-warm and device total'},
                     default=str), flush=True)

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--state',required=True); p.add_argument('--lag',required=True)
    p.add_argument('--dtype',choices=('float32','float64'),required=True)
    p.add_argument('--objective',choices=('mean','var'),required=True)
    p.add_argument('--steps',type=int,required=True)
    p.add_argument('--block',type=int,default=320)
    pilot(p.parse_args())
