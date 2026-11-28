#!/usr/bin/env python3
"""Fail-closed analysis of native OpenCL WALL_GATE0 evidence."""
import csv,json,math,sys
from pathlib import Path
p=Path(sys.argv[1]); rows=list(csv.DictReader(p.open()))
assert len(rows)==2001 and [int(r['step']) for r in rows]==list(range(2001))
def v(r,k):
    z=float(r[k]);assert math.isfinite(z),(r['step'],k);return z
r0=rows[0];px0=v(r0,'px');m0=v(r0,'ddf_mass_offset_all_cells')
fx=0;res=[]
for r in rows:
    if int(r['step']):fx+=v(r,'wall_fx_sum')
    res.append(v(r,'px')-px0-fx)
peak=max(abs(z) for z in res[:21]); mass=max(abs(v(r,'ddf_mass_offset_all_cells')-m0)/abs(m0) for r in rows)
odd=[]
for name in ('ground9_delta','ground16_delta','top15_delta','top10_delta'):
    values=[v(r,name) for r in rows[1:21]]
    odd.append({'name':name,'min':min(values),'max':max(values),'sign_changes':sum(x*y<0 for x,y in zip(values,values[1:]))})
summary={'rows':len(rows),'px0':px0,'max_abs_px_change_no_shear_0to20':max(abs(v(r,'px')-px0) for r in rows[:21]),'max_abs_px_change_no_shear_rel_0to20':max(abs(v(r,'px')-px0)/abs(px0) for r in rows[:21]),'max_abs_ddf_mass_rel':mass,'px_residual20':res[20],'peak_abs_residual0to20':peak,'px_gate':1e-4*abs(px0),'delta':odd,'eligible_step1':int(float(rows[1]['eligible']))}
print(json.dumps(summary,indent=2,ensure_ascii=False))
