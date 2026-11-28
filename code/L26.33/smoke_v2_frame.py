#!/usr/bin/env python3
"""Isolated L26.33 frame diagnostic component; not a B0 or tower result.

All section, loading and stiffness assumptions are provisional until full-length
CRC execution, and none of the generated signals are measured wind/earthquake.
"""
import argparse
import json
import math
import time
from pathlib import Path

import openseespy.opensees as ops

E = 206e9
H = 3.5
B = 6.0
MASS_PER_SQUARE_M = 1000.0
TARGET_TOL = 0.20
POST_YIELD_RATIO = 0.03


def assemble(n=5, bays=1, inertia_scale=1.0, yielding=False,
             yield_factor=1.0):
    ops.wipe()
    ops.model('basic', '-ndm', 2, '-ndf', 3)
    ops.geomTransf('Linear', 1)
    joint = lambda k, j: 1000 + 10*k + j
    floor_mass = bays * B * B * MASS_PER_SQUARE_M
    for k in range(n+1):
        for j in range(bays+1):
            tag = joint(k, j)
            ops.node(tag, B*j, H*k)
            if k == 0:
                ops.fix(tag, 1, 1, 1)
            else:
                ops.mass(tag, floor_mass/(bays+1), floor_mass/(bays+1), 1e-8)
    # These are explicitly assumed section values; tuning changes both I's equally.
    acol, icol, abeam, ibeam = .03, .00055*inertia_scale, .024, .00040*inertia_scale
    spring_k = 2e10  # both the elastic and initial plastic hinge use identical k
    fy = 3e8 * yield_factor
    ops.uniaxialMaterial('Steel01', 1, fy, spring_k, POST_YIELD_RATIO)
    ops.uniaxialMaterial('Elastic', 2, spring_k)
    spring_mat = 1 if yielding else 2
    eid = 1
    hinges = []

    def hinge(master, aux):
        nonlocal eid
        ops.node(aux, *ops.nodeCoord(master))
        ops.equalDOF(master, aux, 1, 2)
        ops.element('zeroLength', eid, master, aux, '-mat', spring_mat, '-dir', 3)
        hinges.append((master, aux, fy/spring_k))
        eid += 1

    for k in range(1, n+1):
        for j in range(bays+1):
            low, high = joint(k-1,j), joint(k,j)
            if k == 1:
                aux = 100000 + eid
                hinge(low, aux)
                low = aux
            ops.element('elasticBeamColumn', eid, low, high, acol, E, icol, 1)
            eid += 1
        for j in range(bays):
            low, high = joint(k,j), joint(k,j+1)
            al, ah = 100000 + eid, 200000 + eid
            hinge(low, al)
            hinge(high, ah)
            ops.element('elasticBeamColumn', eid, al, ah, abeam, E, ibeam, 1)
            eid += 1
    eig = ops.eigen('-genBandArpack', 3)
    if len(eig) != 3 or min(eig) <= 0:
        raise RuntimeError(f'nonpositive/incomplete frame eigenvalues: {eig}')
    periods = [2*math.pi/math.sqrt(x) for x in eig]
    return {'periods_s':periods, 'scale':inertia_scale, 'hinges':hinges,
            'tip_node':joint(n,0), 'yield_moment_Nm':fy,
            'floor_mass_kg':floor_mass}


def calibrate(n=5, bays=1):
    target = .1*n
    scale = 1.0
    history = []
    for iteration in range(12):
        result = assemble(n,bays,scale)
        period = result['periods_s'][0]
        history.append({'iteration':iteration, 'I_scale':scale, 'T1_s':period})
        if abs(period/target - 1) <= .005:
            return scale, history
        # T roughly proportional to I**-1/2; cap update to keep iteration stable
        step = max(.25, min(4.0, (period/target)**2))
        scale *= step
    raise RuntimeError(f'frame calibration did not converge: {history}')


def history_run(n, bays, scale, factor, kind, yielding, dt, seconds):
    model = assemble(n,bays,scale,yielding,factor)
    first, third = model['periods_s'][0], model['periods_s'][2]
    w1, w3 = 2*math.pi/first, 2*math.pi/third
    beta = .04/(w1+w3)
    alpha = beta*w1*w3
    ops.rayleigh(alpha,0.0,0.0,beta)
    if dt > min(model['periods_s'])/20:
        raise ValueError('dt exceeds T_min/20')
    count = round(seconds/dt)
    if abs(count*dt-seconds) > 1e-8:
        raise ValueError('seconds/dt is not integral')
    # Deliberately labeled diagnostic synthetic histories; not a matched design spectrum.
    if kind == 'wind':
        values = [math.sin(2*math.pi*.15*i*dt)+.3*math.sin(2*math.pi*.62*i*dt)
                  for i in range(count+1)]
        scale_force = 10000.0
    elif kind == 'earthquake':
        values = [math.sin(2*math.pi*1.1*i*dt)*math.sin(math.pi*i/count)**2
                  for i in range(count+1)]
        scale_force = 50000.0
    else:
        raise ValueError(kind)
    ops.timeSeries('Path', 7, '-dt', dt, '-values', *values)
    ops.pattern('Plain', 7, 7)
    ops.load(model['tip_node'],scale_force,0.0,0.0)
    ops.constraints('Transformation')
    ops.numberer('RCM')
    ops.system('BandGeneral')
    ops.test('NormDispIncr',1e-7,30)
    ops.algorithm('Newton')
    ops.integrator('Newmark',.5,.25)
    ops.analysis('Transient')
    peak = 0.0
    max_mu = 0.0
    t0 = time.monotonic()
    for i in range(count):
        rc = ops.analyze(1,dt)
        if rc:
            raise RuntimeError(f'{kind} {"nonlinear" if yielding else "linear"} step={i} rc={rc}')
        peak = max(peak,abs(ops.nodeDisp(model['tip_node'],1)))
        if yielding:
            for a,b,theta_y in model['hinges']:
                max_mu = max(max_mu,abs(ops.nodeDisp(a,3)-ops.nodeDisp(b,3))/theta_y)
    return {'kind':kind, 'yielding':yielding, 'steps':count,
            'wall_s':time.monotonic()-t0,'peak_tip_m':peak,
            'mu_max_hinges':max_mu if yielding else None,
            'dt_s':dt, 'duration_s':seconds,'periods_s':model['periods_s']}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--factor',type=float,default=1.0)
    ap.add_argument('--full',action='store_true')
    args=ap.parse_args()
    if args.output.exists():
        ap.error('refuse to overwrite result')
    if args.factor <= 0:
        ap.error('factor must be positive')
    output={'status':'diagnostic_only','assumptions':
            ['5-story 1-bay 2D, 3.5m story, 6m bay, assumed beam/column sections',
             'two-frequency Rayleigh 2%, elastic and plastic springs same initial k',
             'deterministic sinusoidal forces are not measured wind or code-spectrum earthquake'],
            'full_length_requested':args.full}
    try:
        scale,history=calibrate()
        output['calibration']=history
        output['frame']=assemble(inertia_scale=scale)
        target=.5
        output['frame_T1_gate_pass']=abs(output['frame']['periods_s'][0]/target-1)<=TARGET_TOL
        if args.full and output['frame_T1_gate_pass']:
            # A separate production qualification must substitute source-governed loads.
            for kind,seconds in [('wind',600.0),('earthquake',40.0)]:
                for yielding in (False,True):
                    key=f'{kind}_{"plastic" if yielding else "linear"}'
                    # dt chosen from actual shortest modal period, not an asserted fixed step.
                    model=assemble(inertia_scale=scale,yielding=yielding,yield_factor=args.factor)
                    dt=seconds/math.ceil(seconds/(min(model['periods_s'])/25))
                    output[key]=history_run(5,1,scale,args.factor,kind,yielding,dt,seconds)
        output['status']='diagnostic_completed'
    except Exception as exc:
        output['status']='failed'
        output['error']=repr(exc)
        raise
    finally:
        # Only small metadata and statistics, no time-series samples.
        output.pop('frame',None) if output.get('status')=='failed' else None
        with args.output.open('x',encoding='utf8') as f:
            json.dump(output,f,ensure_ascii=False,indent=2,allow_nan=False)
            f.write('\n')
        ops.wipe()


if __name__=='__main__':
    main()
