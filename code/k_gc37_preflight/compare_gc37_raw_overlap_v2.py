#!/usr/bin/env python3
"""Compare archived v1/v2 predicted fields on their exact shared grid."""
import hashlib, json, pathlib, numpy as np
R=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37')
A=R/'gc37_raw_v1'; B=R/'gc37_raw_v2'
CYCLES={'2020060806':5,'2020060706':9,'2020060606':13}
FIELDS=('reg_mean_sea_level_pressure','reg_geopotential','reg_temperature','reg_u_component_of_wind','reg_v_component_of_wind','reg_specific_humidity')
out={'cycles':{},'method':'v2 coordinates intersected to exact v1 lat/lon; float32 elementwise; compare all levels and all 27 forecast steps','fields':FIELDS}
for cycle,n in CYCLES.items():
    rows=[]
    for step in range(1,n+1):
        with np.load(A/cycle/f'step_{step:02d}.npz') as a, np.load(B/cycle/f'step_{step:02d}.npz') as b:
            y=np.searchsorted(b['reg_lat'],a['reg_lat']);x=np.searchsorted(b['reg_lon'],a['reg_lon'])
            assert np.array_equal(b['reg_lat'][y],a['reg_lat']) and np.array_equal(b['reg_lon'][x],a['reg_lon'])
            assert np.array_equal(a['reg_level'],b['reg_level'])
            record={'step':step,'diff':{}}
            for field in FIELDS:
                av=a[field];bv=b[field]
                assert np.isfinite(av).all() and np.isfinite(bv).all(),(cycle,step,field)
                cropped=bv[...,y[:,None],x[None,:]]
                assert cropped.shape==av.shape,(cycle,step,field,cropped.shape,av.shape)
                diff=np.abs(av.astype('float64')-cropped.astype('float64'))
                record['diff'][field]={'max_abs':float(diff.max()),'rmse':float(np.sqrt(np.mean(diff**2))),'exact_equal':bool(np.array_equal(av,cropped))}
            rows.append(record)
    out['cycles'][cycle]=rows
assert sum(map(len,out['cycles'].values()))==27
p=R/'gc37_raw_v2'/'OVERLAP_V1_V2.json'
with p.open('x') as f:json.dump(out,f,indent=2)
print(json.dumps({'report':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'max_abs_by_field':{field:max(r['diff'][field]['max_abs'] for rows in out['cycles'].values() for r in rows) for field in FIELDS}},indent=2))
