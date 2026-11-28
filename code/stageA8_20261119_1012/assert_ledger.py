#!/usr/bin/env python3
"""T17 stage A host-ledger gates. Lattice time is integer solver steps.
Positive drag is the magnitude of ground-on-fluid force in -x; the signed
force in the momentum equation is -drag. Mirror residual is in closure error.
Bounce integral is ten-step trapezoid, with fifty-step sensitivity reported.
No fixture may stand in for a native solver ledger.
"""
import argparse, csv, json, math
from pathlib import Path

REQUIRED=('step','mass_fluid_lattice','px_fluid_lattice','ground_drag_snapshot',
          'eligible_native_columns','ground_drag_integral_10','ground_drag_integral_50')

def load(path):
    with Path(path).open(newline='') as f:
        reader=csv.DictReader(f)
        if not set(REQUIRED).issubset(reader.fieldnames or ()):
            raise ValueError('missing native ledger columns')
        rows=[{k:float(r[k]) for k in REQUIRED} for r in reader]
    if not rows or any(not all(math.isfinite(v) for v in r.values()) for r in rows):
        raise ValueError('empty or nonfinite native ledger')
    steps=[int(r['step']) for r in rows]
    if any(r['step']!=s for r,s in zip(rows,steps)) or steps!=sorted(set(steps)):
        raise ValueError('noninteger, duplicate or unordered step')
    return {int(r['step']):r for r in rows}

def gate_a1(rows, kind):
    a,b=rows[0],rows[1000]
    field='mass_fluid_lattice' if kind=='mass' else 'px_fluid_lattice'
    if not a[field]: raise ValueError('zero denominator')
    err=abs(b[field]-a[field])/abs(a[field])
    return {'relative_change':err,'limit':1e-5,'pass':err<=1e-5}

def gate_a3(rows,nx=256,ny=128):
    target=nx*ny
    return {'eligible':rows[0]['eligible_native_columns'],'expected':target,
            'pass':all(r['eligible_native_columns']==target for r in rows.values())}

def gate_a7(rows,force_lattice,half_steps,group):
    if not (math.isfinite(force_lattice) and force_lattice>0 and half_steps>0):
        raise ValueError('invalid force or window')
    if group not in ('bounce','t4','t15'): raise ValueError('unknown group')
    volume=256*128*64
    bounds=[0,half_steps,2*half_steps] if group=='t15' else [0,half_steps]
    if any(s not in rows for s in bounds): raise ValueError('missing exact T/2 endpoint')
    results=[]
    for lo,hi in zip(bounds,bounds[1:]):
        a,b=rows[lo],rows[hi]
        dx=hi-lo
        drive=force_lattice*volume*dx
        drag=b['ground_drag_integral_10']-a['ground_drag_integral_10']
        residual=(b['px_fluid_lattice']-a['px_fluid_lattice'])-(drive-drag)
        ratio=abs(residual)/(force_lattice*64*256*128*dx)
        drag50=b['ground_drag_integral_50']-a['ground_drag_integral_50']
        result={'from_step':lo,'to_step':hi,'delta_px':b['px_fluid_lattice']-a['px_fluid_lattice'],
                'drive_impulse':drive,'ground_drag_integral_10':drag,
                'ground_drag_integral_50':drag50,
                'bounce_sampling_relative_difference':abs(drag50-drag)/max(abs(drag),1e-30) if group=='bounce' else None,
                'closure_ratio':ratio,'limit':0.01,'pass':ratio<=0.01}
        results.append(result)
    return {'windows':results,'pass':all(x['pass'] for x in results)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('ledger');p.add_argument('--mode',required=True,choices=['a1a','a1b','a3','a7'])
    p.add_argument('--force',type=float);p.add_argument('--half-steps',type=int)
    p.add_argument('--group',choices=['bounce','t4','t15']);p.add_argument('--out',required=True)
    a=p.parse_args();rows=load(a.ledger)
    if a.mode=='a1a': result=gate_a1(rows,'mass')
    elif a.mode=='a1b': result=gate_a1(rows,'momentum')
    elif a.mode=='a3': result=gate_a3(rows)
    else: result=gate_a7(rows,a.force,a.half_steps,a.group)
    Path(a.out).write_text(json.dumps({'mode':a.mode,**result},indent=2)+'\n')
    print(json.dumps({'mode':a.mode,**result}))
    if not result['pass']: raise SystemExit(2)
if __name__=='__main__':main()
