#!/usr/bin/env python3
"""Read-only global upper-level wind maxima for D-X1, both input times."""
import json
import numpy as np
from netCDF4 import Dataset

ROOTS = {
    'N1_2024061418': '/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x/inputs_N1N3N4_v1/input_2024061418_zero.nc',
    'R1_2024073100': '/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37/inputs_2024_R1R2_v1/input_2024073100_zero.nc',
}
records = {}
for case, path in ROOTS.items():
    with Dataset(path) as ds:
        levels = np.asarray(ds.variables['level'][:])
        lat = np.asarray(ds.variables['lat'][:])
        lon = np.asarray(ds.variables['lon'][:])
        rows = []
        for k, p in enumerate(levels):
            if not 1 <= p <= 50:
                continue
            for field in ('u_component_of_wind', 'v_component_of_wind'):
                v = ds.variables[field]
                a = np.asarray(np.ma.filled(v[0, :, k, :, :], np.nan))
                if not np.isfinite(a).all():
                    raise ValueError((case, field, float(p), 'nonfinite'))
                ix = np.unravel_index(np.argmax(np.abs(a)), a.shape)
                rows.append(dict(level_hpa=float(p), field=field, max_abs_m_s=float(abs(a[ix])), signed_m_s=float(a[ix]), time_index=int(ix[0]), latitude=float(lat[ix[1]]), longitude_east=float(lon[ix[2]])))
        records[case] = {'path': path, 'rows': rows, 'maximum': max(rows, key=lambda x: x['max_abs_m_s'])}
print(json.dumps(records, ensure_ascii=False, indent=2))
