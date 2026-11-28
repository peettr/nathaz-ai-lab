#!/usr/bin/env python3
"""Read-only audit of global GFS geopotential masks for R1 t0."""
import json
from pathlib import Path
import numpy as np
import pygrib
root=Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37/inputs_2024_R1R2_v1/raw/2024073100')
for filename in ('gfs.0p25.2024073018.f000.grib2','gfs.0p25b.2024073018.f000.grib2','gfs.0p25.2024073100.f000.grib2','gfs.0p25b.2024073100.f000.grib2'):
    rows=[]
    with pygrib.open(str(root/filename)) as grb:
        for msg in grb.select(shortName='gh', typeOfLevel='isobaricInhPa'):
            a=np.ma.filled(msg.values,np.nan)
            bad=np.argwhere(~np.isfinite(a))
            if len(bad):
                rows.append({'level_hpa':int(msg.level),'count':len(bad),'examples_lat_lon':[(90-float(r)*.25,float(c)*.25) for r,c in bad[:6]],'lat_index_range':[int(bad[:,0].min()),int(bad[:,0].max())]})
    print(json.dumps({'file':filename,'bad_levels':rows}),flush=True)
