#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
t02.py

Gaussian statistical linearization of a TMDI with:
  1. Coulomb friction at the inerter terminals;
  2. displacement-gated inertance.

The specified switching model has continuous displacement and velocity:
no impact impulse or restitution coefficient is introduced.

Joint Gaussian least-squares projection:
    b*g(x)*a ~= beq*a + keq*x
    beq = b * 2*Phi(-h)
    keq = -b * 2*h*phi(h) * sigma_v**2 / sigma_x**2
    h = delta / sigma_x

Coulomb friction:
    Fc*sign(v) ~= ceq*v
    ceq = sqrt(2/pi)*Fc/sigma_v

No Monte Carlo simulation.
Dependencies: numpy, scipy.
Last stdout line: JSON with sigma_q and sigma_stroke for all cases.
"""

import json
import sys
import numpy as np

from scipy.linalg import solve_continuous_lyapunov
from scipy.optimize import least_squares
from scipy.special import ndtr


# -------------------- Parameters --------------------

M = 437000.0
FS = 0.32
WS = 2.0 * np.pi * FS
ZETA = 0.01

MU = 0.01
BETA = 0.05
PHI_B = 0.5

MD = MU * M
B_NOM = BETA * M

K_STRUCT = M * WS**2
C_STRUCT = 2.0 * ZETA * M * WS

U = 30.0
KAPPA = 245.0

NU = 0.9783145940392678
CD = 7276.0250356865

AF = np.array([
    [0.0, 1.0],
    [-0.19278143774341702, -1.9952373861891364]
])
BF = np.array([[0.0], [1.0]])
CF = np.array([[2.790722214048782, 3.5050456221488147]])

CASES = {
    "small": (89.7681475490579, 0.0005364325168720123),
    "medium": (448.8407377452896, 0.0026821625843600617),
    "large": (1346.5222132358685, 0.010728650337440247),
    "X": (448.8407377452896, 0.026821625843600615),
}

EB = np.array([-PHI_B, 1.0])
ED = np.array([-1.0, 1.0])
EBB = np.outer(EB, EB)
EDD = np.outer(ED, ED)

M0 = np.diag([M, MD])
C0 = np.diag([C_STRUCT + KAPPA * U, 0.0]) + CD * EDD
FORCE = np.array([KAPPA * U, 0.0])

LX = np.array([-PHI_B, 1.0, 0.0, 0.0, 0.0, 0.0])
LV = np.array([0.0, 0.0, -PHI_B, 1.0, 0.0, 0.0])
LS = np.array([-1.0, 1.0, 0.0, 0.0, 0.0, 0.0])

B = np.zeros((6, 1))
B[4:6, :] = BF
Q = B @ B.T

SQRT_2_PI = np.sqrt(2.0 / np.pi)


def base_stiffness(nu):
    # IMPORTANT: use nominal inertance, not equivalent inertance.
    kd = (MD + B_NOM) * (nu * WS)**2
    return np.diag([K_STRUCT, 0.0]) + kd * EDD


def equivalent_coefficients(log_sigmas, fc, delta):
    sx, sv = np.exp(log_sigmas)
    h = delta / sx

    # Numerically robust tail probability.
    p_contact = float(2.0 * ndtr(-h))

    # Avoid unnecessary underflow/overflow for extremely large h.
    if h > 38.0:
        tail_moment = 0.0
    else:
        tail_moment = float(
            SQRT_2_PI * h * np.exp(-0.5 * h * h)
        )

    beq = B_NOM * p_contact
    ceq = SQRT_2_PI * fc / sv
    keq = -B_NOM * tail_moment * (sv / sx)**2

    return beq, ceq, keq, p_contact


def build_system(nu, beq, ceq, keq):
    me = M0 + beq * EBB
    ce = C0 + ceq * EBB
    ke = base_stiffness(nu) + keq * EBB

    a = np.zeros((6, 6))
    a[0:2, 2:4] = np.eye(2)
    a[2:4, 0:2] = -np.linalg.solve(me, ke)
    a[2:4, 2:4] = -np.linalg.solve(me, ce)
    a[2:4, 4:6] = np.linalg.solve(me, FORCE[:, None] @ CF)
    a[4:6, 4:6] = AF

    return a


def covariance(a):
    eig_max = float(np.max(np.linalg.eigvals(a).real))
    if not np.isfinite(eig_max) or eig_max >= -1.0e-11:
        raise ValueError("Equivalent system is not strictly stable.")

    pc = solve_continuous_lyapunov(a, -Q)
    pc = 0.5 * (pc + pc.T)

    if not np.all(np.isfinite(pc)):
        raise ValueError("Nonfinite covariance.")

    vx = float(LX @ pc @ LX)
    vv = float(LV @ pc @ LV)
    vq = float(pc[0, 0])
    vs = float(LS @ pc @ LS)

    if min(vx, vv, vq, vs) <= 0.0:
        raise ValueError("Nonpositive response variance.")

    return pc


def evaluate(log_sigmas, fc, delta, nu=NU):
    beq, ceq, keq, p_contact = equivalent_coefficients(
        log_sigmas, fc, delta
    )
    a = build_system(nu, beq, ceq, keq)
    pc = covariance(a)

    sx = np.sqrt(float(LX @ pc @ LX))
    sv = np.sqrt(float(LV @ pc @ LV))

    # Zero residual means Gaussian closure is satisfied.
    residual = np.log([sx, sv]) - log_sigmas

    return {
        "residual": residual,
        "P": pc,
        "A": a,
        "beq": beq,
        "ceq": ceq,
        "keq": keq,
        "p_contact": p_contact,
        "sigma_x": float(sx),
        "sigma_v": float(sv),
        "sigma_q": float(np.sqrt(pc[0, 0])),
        "sigma_stroke": float(np.sqrt(LS @ pc @ LS)),
    }


def residual_for_solver(z, fc, delta, nu):
    try:
        return evaluate(z, fc, delta, nu)["residual"]
    except (ValueError, np.linalg.LinAlgError):
        # A finite penalty allows rejected trial points.
        # Continuation ensures the initial point is close to a valid branch.
        try:
            beq, ceq, keq, _ = equivalent_coefficients(z, fc, delta)
            a = build_system(nu, beq, ceq, keq)
            growth = float(np.max(np.linalg.eigvals(a).real))
            penalty = 20.0 + max(0.0, growth)
        except (ValueError, np.linalg.LinAlgError, OverflowError):
            penalty = 100.0

        return np.array([penalty, penalty])


def solve_local(z0, fc, delta, nu=NU):
    sol = least_squares(
        residual_for_solver,
        z0,
        args=(fc, delta, nu),
        method="trf",
        bounds=(-25.0 * np.ones(2), 10.0 * np.ones(2)),
        xtol=2.0e-12,
        ftol=2.0e-12,
        gtol=2.0e-12,
        max_nfev=300,
        x_scale="jac",
    )

    try:
        result = evaluate(sol.x, fc, delta, nu)
    except (ValueError, np.linalg.LinAlgError):
        return None

    if np.max(np.abs(result["residual"])) > 2.0e-9:
        return None

    return sol.x.copy(), result


def solve_case(fc, delta, nu=NU):
    # Start at the exact linear limit.
    a0 = build_system(nu, B_NOM, 0.0, 0.0)
    p0 = covariance(a0)
    z = np.log([
        np.sqrt(float(LX @ p0 @ LX)),
        np.sqrt(float(LV @ p0 @ LV)),
    ])

    # Adaptive continuation in both nonlinear parameters.
    lam = 0.0
    step = 0.025
    result = evaluate(z, 0.0, 0.0, nu)

    attempts = 0
    while lam < 1.0:
        attempts += 1
        if attempts > 1000:
            raise RuntimeError("Continuation exceeded its iteration limit.")

        target = min(1.0, lam + step)
        answer = solve_local(z, target * fc, target * delta, nu)

        if answer is None:
            step *= 0.5
            if step < 1.0e-6:
                raise RuntimeError(
                    "Unable to continue a stable Gaussian closure "
                    "to Fc={}, delta={}.".format(fc, delta)
                )
            continue

        z, result = answer
        lam = target
        step = min(0.05, 1.4 * step)

    # Re-evaluate at precisely the specified parameters.
    result = evaluate(z, fc, delta, nu)
    result["log_sigmas"] = z
    return result


def self_checks(result):
    pc = result["P"]
    a = result["A"]

    # 1. Lyapunov equation residual.
    ap = a @ pc
    pat = pc @ a.T
    lr = ap + pat + Q
    denom = max(
        np.linalg.norm(ap, ord="fro")
        + np.linalg.norm(pat, ord="fro")
        + np.linalg.norm(Q, ord="fro"),
        1.0e-30,
    )
    lyap_rel = np.linalg.norm(lr, ord="fro") / denom
    if lyap_rel > 1.0e-9:
        raise RuntimeError("Lyapunov residual check failed.")

    # 2. Covariance positive semidefiniteness in normalized coordinates.
    scale = np.sqrt(np.diag(pc))
    corr = pc / scale[:, None] / scale[None, :]
    if np.min(np.linalg.eigvalsh(corr)) < -1.0e-8:
        raise RuntimeError("Covariance PSD check failed.")

    # 3. Stationary identities:
    #       E[x*v] = 0
    #       E[x*a] = -E[v*v]
    # Structural acceleration has no direct white-noise term.
    la = EB @ a[2:4, :]
    sx = result["sigma_x"]
    sv = result["sigma_v"]

    exv = float(LX @ pc @ LV)
    exa = float(LX @ pc @ la)

    if abs(exv) / (sx * sv) > 1.0e-7:
        raise RuntimeError("Stationary E[x*v]=0 check failed.")
    if abs(exa + sv**2) / sv**2 > 1.0e-7:
        raise RuntimeError("Stationary E[x*a]=-E[v^2] check failed.")

    # 4. Nonlinear closure residual.
    if np.max(np.abs(result["residual"])) > 2.0e-9:
        raise RuntimeError("Gaussian closure check failed.")

    return float(lyap_rel)


def check_linear_limit():
    a = build_system(NU, B_NOM, 0.0, 0.0)
    pc = covariance(a)
    z = np.log([
        np.sqrt(float(LX @ pc @ LX)),
        np.sqrt(float(LV @ pc @ LV)),
    ])

    beq, ceq, keq, p_contact = equivalent_coefficients(z, 0.0, 0.0)

    if not (
        beq == B_NOM
        and ceq == 0.0
        and keq == 0.0
        and p_contact == 1.0
    ):
        raise RuntimeError("Exact linear coefficient limit failed.")

    r = evaluate(z, 0.0, 0.0)
    if np.max(np.abs(r["residual"])) > 1.0e-11:
        raise RuntimeError("Exact linear covariance limit failed.")

    self_checks(r)
    return r


def main():
    linear = check_linear_limit()

    # Diagnostics go to stderr, keeping stdout machine-readable.
    print(
        "Linear limit: sigma_q={:.12g}, sigma_stroke={:.12g}".format(
            linear["sigma_q"], linear["sigma_stroke"]
        ),
        file=sys.stderr,
    )

    output = {}
    for name, (fc, delta) in CASES.items():
        result = solve_case(fc, delta)
        lyap_rel = self_checks(result)

        output[name] = {
            "sigma_q": result["sigma_q"],
            "sigma_stroke": result["sigma_stroke"],
        }

        print(
            (
                "{}: p_contact={:.8g}, beq={:.8g} kg, "
                "ceq={:.8g} N*s/m, keq={:.8g} N/m, "
                "sigma_x={:.8g} m, sigma_v={:.8g} m/s, "
                "closure={:.3e}, lyap={:.3e}"
            ).format(
                name,
                result["p_contact"],
                result["beq"],
                result["ceq"],
                result["keq"],
                result["sigma_x"],
                result["sigma_v"],
                float(np.max(np.abs(result["residual"]))),
                lyap_rel,
            ),
            file=sys.stderr,
        )

    # Required last stdout line.
    print(json.dumps(output, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
