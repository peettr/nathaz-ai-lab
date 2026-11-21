#!/usr/bin/env python3.10
"""Read-only reduction of immutable thin fields; writes only alongside this script."""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / 'inlet_reduction.json'
CASES = [('run3', x) for x in ('dx1p0_s101','dx0p5_s101','dx1p0_s102','dx0p5_s102')] + [('T3b_r2', x) for x in ('dx1p0_s103','dx0p5_s103','dx1p0_s104','dx0p5_s104')]
records = []
for group, case in CASES:
    with np.load(ROOT/group/(case+'_thin.npz'), allow_pickle=False) as data:
        u = data['u_avg']; fluid = data['fluid']; meta = json.loads(str(data['metadata']))
    dx = float(meta['dx']); ki = int(meta['k_start']); ox,oy,oz = meta['origin']
    center = (oy+np.asarray(meta['y_indices'])*dx>=40-1e-6)&(oy+np.asarray(meta['y_indices'])*dx<=60+1e-6)
    rec = {'group':group,'case':case,'dx':dx,'source_npz':str(ROOT/group/(case+'_thin.npz')),'stations':{}}
    for x in (0.,1.,2.,5.,252.):
        i = round((x-ox)/dx)
        first = next((ki+j for j in range(fluid.shape[0]) if np.all(fluid[j,center,i]>.5)), None)
        point = {'first_fluid_k':first,'first_fluid_z_m':oz+first*dx if first is not None else None}
        # Two distinct, explicit physical heights: z=2 m above unscaled terrain,
        # and h=2 m above each station's actual numerical-wall flag transition.
        for name, target_z in [('fixed_physical_z2',2.),('local_wall_h2',(oz+(first-.5)*dx+2.) if first is not None else None)]:
            if target_z is None: continue
            zf=(target_z-oz)/dx; k=int(np.floor(zf)); a=zf-k; q=k-ki
            if q<0 or q+1>=fluid.shape[0]: point[name]={'valid':False,'reason':'outside archived support'};continue
            ff0=fluid[q,center,i];ff1=fluid[q+1,center,i]
            valid=bool(np.all(ff0>.5)&np.all(ff1>.5))
            value={'valid':valid,'z_m':target_z,'support_k':[k,k+1],'fluid_min':[float(ff0.min()),float(ff1.min())]}
            if valid:
                v=(1-a)*u[q,center,i,:].astype('f8')+a*u[q+1,center,i,:].astype('f8')
                speed=np.linalg.norm(v,axis=1)
                value.update(G_mps=float(speed.mean()),ux_mps=float(v[:,0].mean()),speed_range_mps=[float(speed.min()),float(speed.max())],y_count=int(center.sum()))
            point[name]=value
        rec['stations'][str(int(x))]=point
    records.append(rec)
by={(r['group'],r['case']):r for r in records}
summary={'within_t3b_r2_x0_fixed_z2_grid_relative_difference':{},'within_t3b_r2_x5_local_wall_grid_relative_difference':{}}
for seed in (103,104):
    a=by['T3b_r2',f'dx1p0_s{seed}']['stations']['0']['fixed_physical_z2']['G_mps']
    b=by['T3b_r2',f'dx0p5_s{seed}']['stations']['0']['fixed_physical_z2']['G_mps']
    summary['within_t3b_r2_x0_fixed_z2_grid_relative_difference'][str(seed)]=abs(b/a-1)
    a=by['T3b_r2',f'dx1p0_s{seed}']['stations']['5']['local_wall_h2']['G_mps']
    b=by['T3b_r2',f'dx0p5_s{seed}']['stations']['5']['local_wall_h2']['G_mps']
    summary['within_t3b_r2_x5_local_wall_grid_relative_difference'][str(seed)]=abs(b/a-1)
OUT.write_text(json.dumps({'cases':records,'summary':summary},ensure_ascii=False,indent=2)+'\n')
print(OUT)
for r in records:
    print(r['group'],r['case'],[(x,v['first_fluid_z_m'],v['fixed_physical_z2'].get('G_mps'),v['local_wall_h2'].get('G_mps')) for x,v in r['stations'].items() if x in ('0','1','5')])
print('summary',summary)
