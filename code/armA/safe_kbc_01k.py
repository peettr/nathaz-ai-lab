"""Local JAX-only KBC regularization probe; does not modify XLB source.

At low nonequilibrium, sp2=<delta_h,delta_h/feq> approaches zero. The
upstream epsilon=1e-32 allows huge derivatives. This diagnostic floors
sp2 at 1e-8 in FP64; the threshold is a numerical hypothesis, not a
validated physical KBC parameter. Its effect must be checked against FD.
"""
from functools import partial
import jax
import jax.numpy as jnp
from xlb.operator import Operator
from xlb.compute_backend import ComputeBackend
from xlb.velocity_set import D2Q9
from xlb.operator.collision.kbc import KBC

class SafeKBC(KBC):
    @Operator.register_backend(ComputeBackend.JAX)
    @partial(jax.jit, static_argnums=(0,))
    def jax_implementation(self, f, feq, rho, u, omega):
        fneq = f - feq
        if not isinstance(self.velocity_set, D2Q9):
            raise NotImplementedError('This local probe is D2Q9 only')
        delta_s = self.decompose_shear_d2q9_jax(fneq) * rho / 4.0
        delta_h = fneq - delta_s
        beta = self.compute_dtype(0.5) * self.compute_dtype(omega)
        inv_beta = 1.0 / beta
        sp1, sp2 = self.compute_entropic_scalar_products(delta_s, delta_h, feq)
        # Both operands of every JAX branch stay finite; no sp1/0 hidden in where.
        denom = jnp.maximum(sp2, self.compute_dtype(1e-8))
        gamma = inv_beta - (2.0 - inv_beta) * sp1 / denom
        return f - beta * (2.0 * delta_s + gamma[None, ...] * delta_h)

def build(*args, **kwargs):
    import flow_stage1_01h as original
    original.KBC = SafeKBC
    return original.build(*args, **kwargs)
