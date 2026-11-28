#!/usr/bin/env python3
"""L26.33 first-stage isolated CRC diagnostic, NOT production or B0 gate.
All numerical choices beyond frozen protocol are explicit assumptions in card.
"""
import argparse
import csv
import json
import math
import os
import time
from pathlib import Path

import openseespy.opensees as ops

E = 200e9
RHO = 7850.0


def rows(path):
    with open(path, newline='', encoding='utf8') as f:
        return list(csv.DictReader(f))


def frame(n=5, bays=1, yielding=False, yield_factor=1.0):
    """One actual plane elastic beam/column frame with concentrated end hinges."""
    ops.wipe()
    ops.model('basic', '-ndm', 2, '-ndf', 3)
    width, height = 6., 3.5
    mass_floor = bays * 6. * 6. * 1000.
    Acol, Icol, Abeam, Ibeam = .03, .00055, .024, .00040
    # EI scale is tuned once from the first eigenvalue to the approved 0.1*N s.
    ops.geomTransf('Linear', 1)
    tag = lambda k, j: 1000 + k * 10 + j
    for k in range(n + 1):
        for j in range(bays + 1):
            t = tag(k, j)
            ops.node(t, j * width, k * height)
            if k == 0:
                ops.fix(t, 1, 1, 1)
            else:
                # masses only on translational coordinates
                ops.mass(t, mass_floor / (bays + 1), mass_floor / (bays + 1), 1e-8)
    # Concentrated springs at column bases and beam ends. Each auxiliary node
    # shares translations with its physical joint; only its rotation differs.
    elastic_moment = 3.0e8 * yield_factor  # diagnostic guess; freeze after smoke
    ops.uniaxialMaterial('Steel01', 1, elastic_moment, 2.0e10, .03)
    ops.uniaxialMaterial('Elastic', 2, 2.0e10)
    spring_mat = 1 if yielding else 2
    eid = 1
    def end_spring(master, aux):
        nonlocal eid
        x, y = ops.nodeCoord(master)
        ops.node(aux, x, y)
        ops.equalDOF(master, aux, 1, 2)
        ops.element('zeroLength', eid, master, aux, '-mat', spring_mat, '-dir', 3)
        eid += 1
    for k in range(1, n + 1):
        for j in range(bays + 1):
            master0, master1 = tag(k-1, j), tag(k, j)
            # hinges at column bases only (the ground-to-first-story joints).
            if k == 1:
                aux = 100000 + eid
                end_spring(master0, aux)
                low = aux
            else:
                low = master0
            ops.element('elasticBeamColumn', eid, low, master1, Acol, E, Icol, 1)
            eid += 1
        for j in range(bays):
            lo, hi = tag(k, j), tag(k, j+1)
            alo, ahi = 100000 + eid, 200000 + eid
            end_spring(lo, alo)
            end_spring(hi, ahi)
            ops.element('elasticBeamColumn', eid, alo, ahi, Abeam, E, Ibeam, 1)
            eid += 1
    eigenvalues = ops.eigen('-genBandArpack', 3)
    frequencies = [math.sqrt(x)/(2*math.pi) for x in eigenvalues]
    if min(frequencies) <= 0:
        raise RuntimeError('frame has nonpositive eigenvalue')
    return {'n': n, 'bays': bays, 'freq_hz': frequencies,
            'target_hz': 10./n, 'yield_moment_Nm': elastic_moment,
            'nodes': (n+1)*(bays+1), 'elements': eid-1}


def rect_angle_inertia(b_mm, t_mm):
    """Unrotated L from two rectangles minus overlap; diagnostic approximation."""
    b, t = b_mm*1e-3, t_mm*1e-3
    parts = [(b*t, b/2, t/2, b*t**3/12, t*b**3/12),
             (b*t, t/2, b/2, t*b**3/12, b*t**3/12),
             (-t*t, t/2, t/2, -t**4/12, -t**4/12)]
    a = sum(p[0] for p in parts)
    x = sum(p[0]*p[1] for p in parts)/a
    y = sum(p[0]*p[2] for p in parts)/a
    ix = sum(p[3]+p[0]*(p[2]-y)**2 for p in parts)
    iy = sum(p[4]+p[0]*(p[1]-x)**2 for p in parts)
    j = 2*b*t**3/3 - t**4/3
    return a, ix, iy, j


def tower(anchor):
    """Anchor-connected 3D beam/truss candidate; compare modes before use."""
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)
    nodes = rows(anchor/'nodes.csv')
    secs = {r['section']: r for r in rows(anchor/'sections.csv')}
    elements = rows(anchor/'elements.csv')
    masses = {int(r['node_id']):float(r['additional_mass_kg'])
              for r in rows(anchor/'nodal_mass.csv')}
    for r in nodes:
        ident = int(r['node_id'])
        xyz = [float(r[f'{axis}_m']) for axis in 'xyz']
        ops.node(ident, *xyz)
        if xyz[2] == 0:
            ops.fix(ident, 1, 1, 1, 1, 1, 1)
    ops.uniaxialMaterial('Steel01', 91, 355e6, E, .03)
    for r in elements:
        s = secs[r['section']]
        a, iy, iz, j = rect_angle_inertia(float(s['b_mm']), float(s['t_mm']))
        eid = int(r['element_id'])
        trans = 1000+eid
        ops.geomTransf('Linear', trans, *[float(r['orient_'+v]) for v in 'xyz'])
        # truss brace with Steel01 is a modeling assumption; other bars beams.
        if r['section'].startswith('brace_'):
            ops.element('truss', eid, int(r['node_i']), int(r['node_j']), a, 91,
                        '-rho', RHO*a)
        else:
            ops.element('elasticBeamColumn', eid, int(r['node_i']),
                        int(r['node_j']), a, E, E/(2*(1+.3)), j, iy, iz,
                        trans, '-mass', RHO*a)
    for r in nodes:
        ident = int(r['node_id'])
        if float(r['z_m']) > 0:
            m = masses[ident]
            ops.mass(ident, m, m, m, .01*m, .01*m, .01*m)
    eig = ops.eigen('-genBandArpack', 3)
    frequencies = [math.sqrt(x)/(2*math.pi) for x in eig]
    if min(frequencies) <= 0:
        raise RuntimeError('tower has nonpositive eigenvalue')
    return {'nodes':len(nodes),'elements':len(elements),'freq_hz':frequencies,
            'anchor_reference_B_first_two_hz':[1.427494840,1.461914642],
            'approximation':'truss braces and local-angle beam inertia, not calibrated ANSYS M/K'}


def transient(seconds=.2, dt=.01):
    """Weak load, short application smoke; cannot count as 600-s sample."""
    ops.timeSeries('Path', 7, '-dt', dt, '-values', *[.02*math.sin(i*dt*2*math.pi)
                    for i in range(int(seconds/dt)+1)])
    ops.pattern('Plain', 7, 7)
    ops.load(1050, 1000., 0., 0.)  # 5th-floor left physical joint
    ops.constraints('Transformation')
    ops.numberer('RCM')
    ops.system('BandGeneral')
    ops.test('NormDispIncr', 1e-7, 20)
    ops.algorithm('Newton')
    ops.integrator('Newmark', .5, .25)
    ops.analysis('Transient')
    t0 = time.monotonic()
    for k in range(int(seconds/dt)):
        rc=ops.analyze(1,dt)
        if rc != 0:
            raise RuntimeError('OpenSees analyze failed step %s rc %s'%(k,rc))
    return {'steps':int(seconds/dt),'elapsed_s':time.monotonic()-t0,
            'tip_displacement_m':ops.nodeDisp(1050,1)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--anchor',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        p.error('output exists')
    out={'status':'diagnostic_only','model_assumptions':
         ['frame 3.5m story; 6m bay; 1t/m2; beam/column I diagnostic',
          'Steel01 spring moment guess 3e8Nm; tower steel yield 355MPa assumed',
          'tower angle beam geometry not guaranteed equal anchor ANSYS formulation']}
    start=time.monotonic()
    try:
        out['frame_linear']=frame()
        out['frame_transient_linear']=transient()
        out['frame_nonlinear']=frame(yielding=True)
        out['frame_transient_nonlinear']=transient()
        out['tower']=tower(args.anchor)
        out['status']='diagnostics_completed_not_B0'
    except Exception as exc:
        out['error']=repr(exc)
        raise
    finally:
        out['wall_s']=time.monotonic()-start
        with args.output.open('x',encoding='utf8') as f:
            json.dump(out,f,indent=2,ensure_ascii=False,allow_nan=False)
            f.write('\n')
        ops.wipe()

if __name__=='__main__':
    main()
