#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
curves.py

Nonstationary covariance of a wind-turbine tower with TMDI.

Run:
    python3 curves.py

The last stdout line is:
    {"C1": [601 variances], "C2": [601 variances]}

Dependencies:
    numpy, scipy
    Python standard library: os, json

No Monte Carlo, network access, or file I/O.
"""

# Set thread limits before importing NumPy/SciPy.
import os

for name in (
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OMP_NUM_THREADS",
    "BLIS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[name] = "1"

import json
import numpy as np
from scipy.linalg import solve_continuous_lyapunov
from scipy.integrate import solve_ivp


# -------------------- Given parameters --------------------

M = 437000.0
FS = 0.32
WS = 2.0 * np.pi * FS
ZETA_S = 0.01

MU = 0.01
BETA = 0.05
PHI_B = 0.5

KAPPA = 245.0
IV = 0.12

NU = 0.9783
ZETA_D = 0.0705

A0 = 0.1927814377
A1 = 1.995237386
C0 = 2.790722214
C1 = 3.505045622
FILTER_SD = 3.63351958814227

TIMES = np.arange(601, dtype=float)


def make_model(nu=NU, zeta_d=ZETA_D):
    """
    Return:
        A_of_U(U): 6x6 augmented drift matrix
        D:         diffusion covariance B B^T
        P0:        stationary covariance at U = 10 m/s
    """
    md = MU * M
    b = BETA * M
    ks = M * WS**2
    cs = 2.0 * ZETA_S * M * WS

    wd = nu * WS
    kd = (md + b) * wd**2
    cd = 2.0 * zeta_d * (md + b) * wd

    mass = np.array([
        [M + b * PHI_B**2, -b * PHI_B],
        [-b * PHI_B, md + b],
    ], dtype=float)

    stiffness = np.array([
        [ks + kd, -kd],
        [-kd, kd],
    ], dtype=float)

    # Mechanical damping excluding the time-varying aerodynamic term.
    damping_mech = np.array([
        [cs + cd, -cd],
        [-cd, cd],
    ], dtype=float)

    af = np.array([
        [0.0, 1.0],
        [-A0, -A1],
    ], dtype=float)

    h = np.array([C0, C1], dtype=float) / FILTER_SD

    e = np.array([1.0, 0.0])
    minv_e = np.linalg.solve(mass, e)

    # A(U) = A_base + U * A_linear + U^2 * A_quadratic.
    a_base = np.zeros((6, 6), dtype=float)
    a_base[0:2, 2:4] = np.eye(2)
    a_base[2:4, 0:2] = -np.linalg.solve(mass, stiffness)
    a_base[2:4, 2:4] = -np.linalg.solve(mass, damping_mech)
    a_base[4:6, 4:6] = af

    a_linear = np.zeros((6, 6), dtype=float)

    # Aerodynamic damping: -M^{-1} e * kappa U * q_dot.
    a_linear[2:4, 2] = -KAPPA * minv_e

    a_quadratic = np.zeros((6, 6), dtype=float)

    # Force: e * kappa * Iv * U^2 * h * x_f.
    a_quadratic[2:4, 4:6] = (
        KAPPA * IV * np.outer(minv_e, h)
    )

    def a_of_u(u):
        return a_base + u * a_linear + (u * u) * a_quadratic

    # B = [0, 0, 0, 0, 0, 1]^T.
    diffusion = np.zeros((6, 6), dtype=float)
    diffusion[5, 5] = 1.0

    a10 = a_of_u(10.0)

    if np.max(np.linalg.eigvals(a10).real) >= 0.0:
        raise RuntimeError("The U=10 initial system is not Hurwitz.")

    # SciPy solves A P + P A^T = Q.
    p0 = solve_continuous_lyapunov(a10, -diffusion)
    p0 = 0.5 * (p0 + p0.T)

    if not np.all(np.isfinite(p0)) or p0[0, 0] <= 0.0:
        raise RuntimeError("Invalid initial stationary covariance.")

    return a_of_u, diffusion, p0


def variance_curve(
    tau,
    model,
    rtol=1.0e-9,
    atol=1.0e-12,
    max_step=0.5,
):
    """Compute q variance at t = 0, 1, ..., 600 s."""
    a_of_u, diffusion, p0 = model

    def rhs(t, y):
        u = 10.0 + 20.0 * np.exp(-((t - 300.0) / tau)**2)
        a = a_of_u(u)

        p = y.reshape(6, 6)
        dp = a @ p + p @ a.T + diffusion
        return dp.ravel()

    sol = solve_ivp(
        rhs,
        t_span=(0.0, 600.0),
        y0=p0.ravel(),
        method="DOP853",
        t_eval=TIMES,
        rtol=rtol,
        atol=atol,
        max_step=max_step,
    )

    if not sol.success:
        raise RuntimeError("Covariance integration failed: " + sol.message)

    if sol.y.shape != (36, 601):
        raise RuntimeError("Unexpected integration output shape.")

    # Row-major flattening: P[0, 0] is component zero.
    var_q = sol.y[0, :].copy()

    if not np.all(np.isfinite(var_q)):
        raise RuntimeError("Non-finite displacement variance.")

    # Do not clip negative values: that could conceal an integration error.
    if np.any(var_q < 0.0):
        raise RuntimeError("Negative displacement variance.")

    return var_q


def main():
    # Both cases use exactly the same stationary initial covariance.
    model = make_model()

    c1 = variance_curve(tau=60.0, model=model)
    c2 = variance_curve(tau=10.0, model=model)

    output = {
        "C1": c1.tolist(),
        "C2": c2.tolist(),
    }

    # The required JSON is the last (and only) stdout line.
    print(json.dumps(output, allow_nan=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
