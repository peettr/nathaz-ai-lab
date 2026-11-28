#!/usr/bin/env python3
"""OFCL/BEST 34/50/64-kt wind radii -> CLIMADA 6.1.0 H08 RMW.

No station wind or observational error enters this fit. H08's pressure-based B is
computed by CLIMADA itself and never optimized. Input radii are nautical miles.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite, log, sin, pi

NMI_M = 1852.0
KT_MS = 0.5144444444444445
WEIGHTS = {34: 1, 50: 2, 64: 3}

class RadiusUnavailable(ValueError):
    """No usable two-threshold wind-radii fit; do not fabricate fallback RMW."""

@dataclass(frozen=True)
class Node:
    lat_deg: float
    vmax_kt: float
    central_hpa: float
    environmental_hpa: float
    previous_central_hpa: float
    hours_since_previous: float
    translation_ms: float
    radii_nmi: dict[int, tuple[float, ...]]


def prior_nmi(vmax_kt: float, lat_deg: float) -> float:
    """Knaff et al. 2007 North Atlantic prior, not a measured RMW."""
    return 36.1 - 0.0492 * vmax_kt + 0.5740 * (abs(lat_deg) - 25)


def _h08_profile(node: Node, rmw_nmi: float, radii_nmi):
    """Call CLIMADA H08's own angular-speed function, no shadow port of B."""
    import numpy as np
    import xarray as xr
    from climada.hazard.trop_cyclone import trop_cyclone_windfields as wf
    pdelta = (node.environmental_hpa - node.central_hpa) * 100
    ds = xr.Dataset({
        'lat': ('time', [node.lat_deg]),
        'cen': ('time', [node.central_hpa * 100]),
        'pdelta': ('time', [pdelta]),
        'rad': ('time', [rmw_nmi * NMI_M]),
        'cp': ('time', [2 * 7.29e-5 * sin(abs(node.lat_deg)*pi/180)]),
        'tstep': ('time', [node.hours_since_previous * 3600]),
        'vtrans_norm': ('time', [node.translation_ms]),
    })
    # The library's first-node dp/dt is zero; supply a preceding node to retain
    # the supplied preceding pressure and the actual pressure tendency at node 1.
    earlier = ds.copy(deep=True)
    earlier['cen'][:] = node.previous_central_hpa * 100
    earlier['pdelta'][:] = (node.environmental_hpa-node.previous_central_hpa)*100
    ds = xr.concat((earlier, ds), dim='time').assign_coords(time=[0, 1])
    dist = np.asarray([radii_nmi], dtype=float).repeat(2, axis=0)*NMI_M
    mask = np.ones_like(dist, dtype=bool)
    result = wf._compute_angular_windspeeds_h08(ds, dist, mask)
    b = float(ds['hol_b'].values[-1])
    return result[-1] / KT_MS, b


def predicted_outer_radius(node: Node, rmw_nmi: float, threshold: int) -> tuple[float, float]:
    # Entirely independent of station observations. Outermost outward crossing.
    import numpy as np
    grid = np.geomspace(max(0.1, rmw_nmi), 600, 240)
    speeds, b = _h08_profile(node, rmw_nmi, grid)
    crossings = np.where((speeds[:-1] >= threshold) & (speeds[1:] < threshold))[0]
    if not len(crossings):
        raise RadiusUnavailable(f'H08 has no outer {threshold}-kt crossing')
    j = int(crossings[-1]); lo, hi = float(grid[j]), float(grid[j+1])
    for _ in range(10):
        mid = (lo+hi)/2
        speed, _ = _h08_profile(node, rmw_nmi, [mid])
        if speed[0] >= threshold: lo = mid
        else: hi = mid
    return (lo+hi)/2, b


def fit_rmw(node: Node, bounds=(5.0, 200.0), prior_weight=0.25,
            weights=WEIGHTS) -> dict:
    if not all(isfinite(x) for x in (node.lat_deg, node.vmax_kt, node.central_hpa,
            node.environmental_hpa, node.previous_central_hpa,
            node.hours_since_previous, node.translation_ms)):
        raise RadiusUnavailable('nonfinite input')
    if node.environmental_hpa <= node.central_hpa or node.hours_since_previous <= 0 or node.translation_ms < 0:
        raise RadiusUnavailable('invalid pressure, time step, or motion')
    prior = prior_nmi(node.vmax_kt, node.lat_deg)
    if not bounds[0] <= prior <= bounds[1]:
        raise RadiusUnavailable('climatological RMW outside bounds')
    valid = {k: tuple(v for v in vals if isfinite(v) and v > 0)
             for k, vals in node.radii_nmi.items() if k in WEIGHTS and k < node.vmax_kt}
    valid = {k: vals for k, vals in valid.items() if len(vals) >= 2}
    if len(valid) < 2:
        raise RadiusUnavailable('fewer than two distinct thresholds with two quadrants')
    def objective(log_r):
        rmw = __import__('math').exp(log_r)
        try:
            terms = []
            for k, vals in valid.items():
                pred, b = predicted_outer_radius(node, rmw, k)
                if not 0.5 <= b <= 4.0:
                    raise RadiusUnavailable('H08 B outside diagnostic bounds')
                terms.append(weights[k] / len(vals) * sum(log(pred / obs)**2 for obs in vals))
            return sum(terms) + prior_weight*log(rmw/prior)**2
        except RadiusUnavailable:
            return float('inf')
    import numpy as np
    grid = np.linspace(log(bounds[0]), log(bounds[1]), 61)
    values = [(objective(float(v)), float(v)) for v in grid]
    score, center = min(values)
    if not isfinite(score):
        raise RadiusUnavailable('H08 unable to reproduce two wind thresholds')
    idx = next(i for i,v in enumerate(grid) if v == center)
    a, b = float(grid[max(0,idx-1)]), float(grid[min(len(grid)-1,idx+1)])
    golden = (5**0.5-1)/2
    c, d = b-golden*(b-a), a+golden*(b-a)
    fc, fd = objective(c), objective(d)
    for _ in range(55):
        if fc < fd:
            b,d,fd = d,c,fc; c=b-golden*(b-a); fc=objective(c)
        else:
            a,c,fc = c,d,fd; d=a+golden*(b-a); fd=objective(d)
    candidates = values + [(objective((a+b)/2), (a+b)/2)]
    score, best = min(candidates)
    rmw = __import__('math').exp(best)
    _, hol_b = predicted_outer_radius(node, rmw, min(valid))
    return {'rmw_nmi': rmw, 'objective': score, 'h08_b': hol_b,
            'prior_nmi': prior, 'thresholds': sorted(valid),
            'quadrants': {str(k): len(v) for k,v in valid.items()}}
