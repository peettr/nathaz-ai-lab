#!/usr/bin/env python3.10
"""Read-only partial Case E thin-mask wall geometry count (not complete native flags)."""
import json,numpy as np
from pathlib import Path
SRC=Path(__file__).resolve().parents[1]/'R21.4a_T5_caseE_WM_retry2/evidence/E_s102_off_thin.npz'
with np.load(SRC) as d:
    fluid=d['fluid'].astype(bool)
    meta=json.loads(str(d['metadata']))
solid=~fluid
# Internal x/y/z support only, no unarchived outside-slab values inferred.
c=fluid[1:-1,2:-2,2:-2]
xp=solid[1:-1,2:-2,3:-1];xm=solid[1:-1,2:-2,1:-3]
yp=solid[1:-1,3:-1,2:-2];ym=solid[1:-1,1:-3,2:-2]
zp=solid[2:,2:-2,2:-2];zm=solid[:-2,2:-2,2:-2]
ns=xp.astype('u1')+xm+yp+ym
# Counts refer ONLY to k=21..45, x/y interior and archived scalar fluid mask.
r=dict(source=str(SRC),coverage=dict(k_start=meta['k_start']+1,k_end_inclusive=meta['k_end_exclusive']-2,x_start=2,x_end_inclusive=fluid.shape[2]-3,y_start=2,y_end_inclusive=fluid.shape[1]-3),fluid_cells=int(c.sum()),single_horizontal_normal=int((c&(ns==1)).sum()),multiple_horizontal_normals_native_bounce=int((c&(ns>=2)).sum()),facade_and_ground_or_roof_native_bounce=int((c&(ns>=1)&(zp|zm)).sum()),eligible_partial=int((c&(ns==1)&~zp&~zm).sum()),note='Thin VTK scalar-fluid mask only; NOT full Case E native flags or measured flag equality.')
out=Path(__file__).with_name('partial_geometry_count.json');out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
