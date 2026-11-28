#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可选优化脚本；需与 curves.py 位于同一目录。
运行：python3 opt.py
"""

# 先导入 curves，使单线程设置在数值库导入前生效。
from curves import variance_curve

import json
import numpy as np
from scipy.optimize import minimize


LOWER = np.array([0.90, 0.002])
UPPER = np.array([1.10, 0.20])
WIDTH = UPPER - LOWER


def decode(y):
    return LOWER + WIDTH * np.asarray(y, dtype=float)


def main():
    cache = {}
    best_value = np.inf
    best_x = None

    def objective(y):
        nonlocal best_value, best_x

        y = np.asarray(y, dtype=float)
        if np.any(y < 0.0) or np.any(y > 1.0):
            return np.inf

        key = tuple(y.tolist())
        if key in cache:
            return cache[key]

        nu, zd = decode(y)
        v = variance_curve(
            tau=10.0,
            nu=float(nu),
            zeta_d=float(zd),
            rtol=1.0e-8,
            atol=1.0e-12,
            max_step=1.0,
        )

        # 常数缩放仅用于改善优化器的目标数值尺度。
        value = float(np.max(v) / 1.0e-4)
        cache[key] = value

        if value < best_value:
            best_value = value
            best_x = np.array([nu, zd])

        return value

    starts = [
        np.array([0.9783, 0.0705]),
        np.array([0.94, 0.025]),
        np.array([1.04, 0.14]),
    ]

    for x0 in starts:
        y0 = (x0 - LOWER) / WIDTH
        minimize(
            objective,
            y0,
            method="Powell",
            bounds=[(0.0, 1.0), (0.0, 1.0)],
            options={
                "xtol": 2.0e-5,
                "ftol": 2.0e-7,
                "maxiter": 40,
                "maxfev": 120,
                "disp": False,
            },
        )

    if best_x is None:
        raise RuntimeError("Optimization produced no valid candidate.")

    # 对最优候选以脚本 A 的精度重新计算，确认响应有限。
    checked = variance_curve(
        tau=10.0,
        nu=float(best_x[0]),
        zeta_d=float(best_x[1]),
    )
    if not np.all(np.isfinite(checked)):
        raise RuntimeError("Final candidate verification failed.")

    output = {
        "opt_C2": {
            "nu": float(best_x[0]),
            "zeta_d": float(best_x[1]),
        }
    }
    print(json.dumps(output, allow_nan=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
