#!/usr/bin/env python3
"""Read-only N3 q exceedance diagnostic, frozen D-X3 criteria."""
import json
from pathlib import Path
import numpy as np
import pygrib
import xarray as xr

root = Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x/inputs_N1N3N4_v1')
ds = xr.open_dataset(root / 'input_2022070418_zero.nc')
lats = ds.lat.values
lons = ds.lon.values
out = {'source': str(root / 'input_2022070418_zero.nc'), 'levels': {}, 'd01_bbox': '29–58N, 124–72W', 'threshold': [0, 0.04]}
for ti, stamp in enumerate(('2022070412', '2022070418')):
    raw = root / 'raw' / '2022070418' / f'gfs.0p25.{stamp}.f000.grib2'
    grbs = pygrib.open(str(raw))
    msg = grbs.select(shortName='sp', typeOfLevel='surface')[0]
    glat, glon = msg.latlons()
    assert np.isclose(glat[0, 0], lats[-1]) and np.isclose(glat[-1, 0], lats[0])
    assert np.isclose(glon[0, 0], lons[0])
    ps = np.flipud(np.asarray(msg.values))  # GRIB north→south; NetCDF south→north
    assert ps.shape == (len(lats), len(lons)), (ps.shape, len(lats), len(lons))
    entries = []
    for lev in (975, 1000):
        li = int(np.flatnonzero(ds.level.values == lev)[0])
        q = ds.specific_humidity.isel(batch=0, time=ti, level=li).values
        assert q.shape == ps.shape
        viol = np.isfinite(q) & ((q < 0) | (q > .04))
        yi, xi = np.where(viol)
        cell_count = q.size
        cells = []
        for y, x in zip(yi, xi):
            lat, lon = float(lats[y]), float(lons[x])
            cells.append({'lat':lat,'lon_east':lon,'lon_signed':lon if lon <= 180 else lon-360,
                          'q_kgkg':float(q[y,x]),'psfc_pa':float(ps[y,x]),
                          'below_ground':bool(ps[y,x] < lev*100),
                          'd01_bbox':bool(29 <= lat <= 58 and 236 <= lon <= 288)})
        mn = np.unravel_index(np.nanargmin(q),q.shape)
        mx = np.unravel_index(np.nanargmax(q),q.shape)
        def extremum(idx):
            y,x=idx; lon=float(lons[x]); return {'q_kgkg':float(q[y,x]),'lat':float(lats[y]),'lon_east':lon,'lon_signed':lon if lon<=180 else lon-360,'psfc_pa':float(ps[y,x])}
        entries.append({'level_hpa':lev,'count':int(len(cells)),'total_cells':int(cell_count),
                        'fraction':float(len(cells)/cell_count), 'min':extremum(mn),'max':extremum(mx),
                        'negative_count':int(np.count_nonzero(q<0)), 'high_count':int(np.count_nonzero(q>.04)),
                        'd01_bbox_count':sum(c['d01_bbox'] for c in cells),
                        'cells':cells if len(cells)<3000 else None})
    out['levels'][stamp]=entries
    grbs.close()
print(json.dumps(out,ensure_ascii=False,allow_nan=False))
