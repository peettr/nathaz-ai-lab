#!/usr/bin/env python3
"""T03 v3 raw, input-anchored statistics. Run only on CRC compute nodes.

The result preserves censored length scales as null. No calibration thresholds
or scientific judgments are computed here.
"""
import argparse
import json
import math
import re
from pathlib import Path

import numpy as np

HEIGHTS = (0.1, 0.3, 0.5, 0.9, 1.5)
COMPONENTS = ('xx', 'xy', 'xz', 'yy', 'yz', 'zz')
NUM = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?'


def target(case):
    p = case / 'constant/boundaryData/inlet'
    points = np.array([list(map(float, re.findall(NUM, line))) for line in (p/'points').read_text().splitlines() if line.lstrip().startswith('(') and len(re.findall(NUM, line)) == 3])
    def field(name, n):
        return np.array([list(map(float, re.findall(NUM, line))) for line in (p/name).read_text().splitlines() if len(re.findall(NUM, line)) == n and line.strip() != '164'])
    u = field('U', 1).ravel()
    r = field('R', 6)
    l = field('L', 9)
    psi = field('psi', 1).ravel()
    if not (len(points) == len(u) == len(r) == len(l) == len(psi) == 164):
        raise ValueError('expected 164 input points in each boundaryData file')
    return {str(z): {'U': float(np.interp(z, points[:,2], u)),
                     'psi_deg': float(np.interp(z, points[:,2], psi)),
                     'R': dict(zip(COMPONENTS, (float(np.interp(z, points[:,2], r[:,i])) for i in range(6)))),
                     'L': np.stack([np.interp(z, points[:,2], l[:,i]) for i in range(9)]).reshape(3,3).tolist()}
            for z in HEIGHTS}


def first_zero_integral(cov, spacing):
    a = np.asarray(cov, dtype=float)
    if len(a) < 4 or not np.all(np.isfinite(a)) or a[0] <= 0:
        return {'value_m': None, 'censored': True, 'reason': 'insufficient_or_nonfinite'}
    rho = a/a[0]
    crossing = np.flatnonzero(rho[1:] <= 0)
    if not len(crossing):
        return {'value_m': None, 'censored': True, 'lower_bound_m': float(np.trapezoid(rho, dx=spacing)), 'max_lag_m': float((len(a)-1)*spacing)}
    j = int(crossing[0])+1
    fraction = rho[j-1]/(rho[j-1]-rho[j])
    val = np.trapezoid(rho[:j], dx=spacing) + 0.5*rho[j-1]*fraction*spacing
    return {'value_m': float(val), 'censored': False, 'zero_lag_m': float((j-1+fraction)*spacing)}


def read_vectors(path, nprobe):
    rows = []
    last = None
    with path.open() as fh:
        for line in fh:
            if not line.strip() or line.startswith('#'):
                continue
            t = float(line.split(None, 1)[0])
            if t < 5.-1e-8 or t > 120.+1e-8:
                continue
            tick = round(t/.005)
            if abs(t - tick*.005) > 1e-7:
                continue
            if last is not None and t <= last:
                raise ValueError(f'nonmonotone retained probe time: {t}')
            val = np.fromstring(line.translate(str.maketrans('()', '  ')), sep=' ')
            if len(val) != 1 + 3*nprobe:
                raise ValueError(f'expected {nprobe} vectors, got {len(val)} fields: {path}')
            rows.append(val)
            last = t
    if not rows or rows[-1][0] < 119.99:
        raise ValueError(f'incomplete 5–120 s record at {path}')
    a = np.asarray(rows)
    if not np.allclose(np.diff(a[:,0]), .005, atol=1e-6, rtol=.01):
        raise ValueError('irregular retained sampling grid')
    return a[:,0], a[:,1:].reshape(-1, 5, nprobe//5, 3)


def autocov(x, maxlag):
    x = x - x.mean(axis=0)
    n = len(x)
    fft = np.fft.rfft(x, n=1 << (2*n-1).bit_length(), axis=0)
    cov = np.fft.irfft((fft*fft.conj()).real, n=1 << (2*n-1).bit_length(), axis=0)[:maxlag+1]
    return (cov/(n-np.arange(maxlag+1))[:,None]).mean(axis=1)


def spacetime_cov(x, dt, psi, speed, dy):
    ny = x.shape[1]
    values = [float(np.mean(x*x))]
    for lag in range(1, ny):
        projected = lag*dy*math.cos(psi)
        shift = projected*math.tan(psi)/speed if speed > 0 else 0
        k = int(math.floor(shift/dt))
        f = shift/dt-k
        if k+1 >= len(x):
            break
        left = x[:len(x)-k-1, :ny-lag]
        right = (1-f)*x[k:len(x)-1, lag:]+f*x[k+1:,lag:]
        values.append(float(np.mean(left*right)))
    return first_zero_integral(values, dy*math.cos(psi))


def rho(r, key):
    i, j = key
    return r[key]/math.sqrt(r[i+i]*r[j+j])


def load(case, dy=.05):
    input_values = target(case)
    files = sorted((case/'postProcessing/InletPatch').glob('*/U'))
    if len(files) != 1:
        raise ValueError(f'expected one patch probe file, found {len(files)} in {case}')
    # 36 cell-centred probes per height on the 0.05 m inlet grid, -0.875 to 0.875.
    time, v = read_vectors(files[0], 180)
    out = {}
    for iz, z in enumerate(HEIGHTS):
        key = str(z)
        t = input_values[key]
        psi = math.radians(t['psi_deg'])
        c, s = math.cos(psi), math.sin(psi)
        raw = v[:,iz,:,:]
        local = raw @ np.array([[c,-s,0],[s,c,0],[0,0,1]])
        global_mean = raw.mean(axis=(0,1))
        fluct = local-local.mean(axis=0, keepdims=True)
        cov = np.einsum('tyi,tyj->ij',fluct,fluct)/fluct.shape[0]/fluct.shape[1]
        R = dict(zip(COMPONENTS, (float(cov[0,0]),float(cov[0,1]),float(cov[0,2]),float(cov[1,1]),float(cov[1,2]),float(cov[2,2]))))
        speed = float(np.linalg.norm(global_mean[:2]))
        length_x = {}
        length_y = {}
        for component, label in enumerate('xyz'):
            series = fluct[:,:,component]
            length_x[label] = first_zero_integral(autocov(series, min(len(time)//3,6000)), .005*speed)
            length_y[label] = spacetime_cov(series, .005, psi, speed, dy)
        direction = float(math.degrees(math.atan2(global_mean[1],global_mean[0])))
        inp = t['R']
        out[key] = {'z_m':z, 'target_psi_deg':t['psi_deg'], 'direction_deg':direction,
            'direction_abs_error_deg': abs((direction-t['psi_deg']+180)%360-180),
            'mean_global_mps':global_mean.tolist(), 'mean_speed_mps':speed,
            'speed_abs_relative_error_input':abs(speed/t['U']-1), 'R_local':R,
            'diag_in':{k:abs(R[k]/inp[k]-1) for k in ('xx','yy','zz')},
            'rho_in':{k:abs(rho(R,k)-rho(inp,k)) for k in ('xy','xz','yz')},
            'rho_xz_signed_input_delta':rho(R,'xz')-rho(inp,'xz'),
            'Lx_local':length_x, 'Ly_local':length_y,
            'e_Ly_local_x':None if length_y['x']['value_m'] is None else abs(length_y['x']['value_m']/t['L'][0][1]-1)}
    return {'schema':'L22_6_T03_stage0_raw_v3', 'source_case':str(case),
            'source_probe':str(files[0]), 'record_last_s':float(time[-1]),
            'probe_spacing_m':dy, 'target':input_values, 'heights':out,
            'max_speed_in':max(v['speed_abs_relative_error_input'] for v in out.values()),
            'max_diag_in':max(max(v['diag_in'].values()) for v in out.values()),
            'max_rho_in':max(max(v['rho_in'].values()) for v in out.values()),
            'rho_xz_z15_signed_input_delta':out['1.5']['rho_xz_signed_input_delta'],
            'e_Ly':max((v['e_Ly_local_x'] for v in out.values() if v['e_Ly_local_x'] is not None),default=None),
            'censored_heights':sum(v['Ly_local']['x']['censored'] for v in out.values())}


def main():
    p=argparse.ArgumentParser(); p.add_argument('case',type=Path); p.add_argument('output',type=Path)
    a=p.parse_args()
    result=load(a.case)
    if a.output.exists():
        raise FileExistsError(a.output)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'output':str(a.output),'max_rho_in':result['max_rho_in']}))

if __name__=='__main__': main()
