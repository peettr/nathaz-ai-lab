"""L26.22 arm A: XLB JAX inlet-gradient diagnostic; run only on allocated GPU.

Provisional integration probe, NOT a frozen physics case. No self-written LBM.
"""
import argparse
import json
import time
import numpy as np
import jax
import jax.numpy as jnp
import xlb
from xlb.compute_backend import ComputeBackend
from xlb.precision_policy import PrecisionPolicy
from xlb.grid import grid_factory
from xlb.velocity_set import D2Q9
from xlb.operator.boundary_condition import RegularizedBC, HalfwayBounceBackBC, ExtrapolationOutflowBC
from xlb.operator.stepper import IncompressibleNavierStokesStepper


def make_case(nx=48, ny=32):
    """Build once: masks/initial field are identical for AD and FD."""
    xlb.init(velocity_set=D2Q9(precision_policy=PrecisionPolicy.FP32FP32,
                               compute_backend=ComputeBackend.JAX),
             default_backend=ComputeBackend.JAX,
             default_precision_policy=PrecisionPolicy.FP32FP32)
    grid = grid_factory((nx, ny), compute_backend=ComputeBackend.JAX)
    box = grid.bounding_box_indices()
    inner = grid.bounding_box_indices(remove_edges=True)
    inlet = inner['left']
    outlet = inner['right']
    walls = [box['bottom'][k] + box['top'][k] for k in range(2)]
    walls = np.unique(np.array(walls), axis=-1).tolist()
    # At most one fluid-side BC per lattice node. Roughness is smooth porous drag, not a hard stair-step solid.
    def profile():
        return jnp.stack([jnp.full((1, ny), .025), jnp.zeros((1, ny))], axis=0)
    bc = RegularizedBC('velocity', profile=profile, indices=inlet)
    stepper = IncompressibleNavierStokesStepper(
        grid=grid,
        boundary_conditions=[HalfwayBounceBackBC(indices=walls), bc,
                             ExtrapolationOutflowBC(indices=outlet)],
        collision_type='SmagorinskyLESBGK')
    f0, f1, bcm, mm = stepper.prepare_fields()
    return stepper, bc, (f0, f1, bcm, mm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--steps', type=int, default=8)
    ap.add_argument('--nx', type=int, default=48)
    ap.add_argument('--ny', type=int, default=32)
    args = ap.parse_args()
    if args.steps < 2: raise ValueError('steps must be >=2')
    stepper, inlet, fields = make_case(args.nx, args.ny)
    f0, f1, bcm, mm = fields
    seed = 26022
    rng = np.random.default_rng(seed)
    noise = jnp.asarray(rng.standard_normal((args.steps, 8)), dtype=jnp.float32)
    yy = jnp.arange(args.ny)
    bands = jnp.minimum(7, (yy * 8 // args.ny))
    omega = 1.0 / (3 * (.025 * args.ny / 100.) + .5)
    probe_y = jnp.asarray(np.linspace(3, args.ny-4, 12, dtype=np.int32))
    # 8 speed means, 8 stochastic amplitudes, 2 heights; geometry/drag is not yet wired.
    # Fail closed: don't call an 18-control experiment when last 2 controls are inactive.
    command = jnp.r_[jnp.full((8,), .025), jnp.full((8,), .002), jnp.array([4., 7.])]

    def objective(c):
        # XLB's profile is evaluated during prepare_fields, not each step; updating
        # prescribed_values within JIT is an API experiment, not guaranteed differentiable.
        def evolve(c):
            state = (f0, f1)
            samples = []
            lag = jnp.full((8,), .025)
            for t in range(args.steps):
                lag = lag + (c[:8]-lag) / 5.0
                inlet.prescribed_values = jnp.stack([
                    (lag + c[8:16] * noise[t])[bands], jnp.zeros((args.ny,))], axis=0)[:,None,:]
                a,b = stepper(state[0], state[1], bcm, mm, omega, t)
                state = b,a
                _, velocity = stepper.macroscopic(b)
                samples.append(velocity[0, args.nx-6, probe_y])
            return jnp.stack(samples)
        u = evolve(c)
        return jnp.square(jnp.mean(u,axis=0)-.022).sum()

    t0=time.perf_counter()
    try:
        value, grad = jax.value_and_grad(objective)(command)
        value.block_until_ready()
        g = np.asarray(grad)
        # One-dimensional FD is diagnostic only; full 18-vector FD needs a valid case.
        step = .0005
        plus = np.asarray(command).copy(); minus=plus.copy()
        plus[0]+=step; minus[0]-=step
        fd = (float(objective(jnp.asarray(plus)))-float(objective(jnp.asarray(minus))))/(2*step)
        print(json.dumps({'state':'provisional_inlet_probe','seed':seed,'steps':args.steps,
                          'value':float(value),'g_ad_0':float(g[0]),'g_fd_0':fd,
                          'ad_gradient_18':g.tolist(),'seconds':time.perf_counter()-t0,
                          'warning':'roughness controls not yet wired; no cosine or scientific decision'}),flush=True)
    except Exception as exc:
        print(json.dumps({'state':'integration_failed','type':type(exc).__name__,
                          'error':str(exc),'seconds':time.perf_counter()-t0}),flush=True)
        raise

if __name__ == '__main__': main()
