"""L26.20 D1: nearest-neighbour sample GOES-16 ABI CMIPC BT (2 km) onto the fixed WRF d02 grid (3 km).
usage: python goes_remap_v2.py wrfout_template rawdir outdir [C|F]  (v2: product sector arg, scan mode wildcard)
Forward geostationary projection (GOES-R PUG Vol.3 sec 4.2.8): lat/lon -> scan angles (x,y). No parallax correction (descriptive note)."""
import sys, glob, os, re, numpy as np, netCDF4 as N
wrf, raw, out = sys.argv[1:4]; PRD = sys.argv[4] if len(sys.argv) > 4 else 'C'; os.makedirs(out, exist_ok=True)
d = N.Dataset(wrf); lat = np.radians(d['XLAT'][0].astype('f8')); lon = np.radians(d['XLONG'][0].astype('f8')); d.close()
files = sorted(glob.glob(raw + '/OR_ABI-L2-CMIP%s-M*C13_*.nc' % PRD))
g = N.Dataset(files[0]); p = g['goes_imager_projection']
req, rpol, H = p.semi_major_axis, p.semi_minor_axis, p.perspective_point_height + p.semi_major_axis
l0 = np.radians(p.longitude_of_projection_origin); x = g['x'][:].astype('f8'); y = g['y'][:].astype('f8'); g.close()
e2 = (req**2 - rpol**2) / req**2
phc = np.arctan(rpol**2 / req**2 * np.tan(lat)); rc = rpol / np.sqrt(1 - e2 * np.cos(phc)**2)
sx = H - rc * np.cos(phc) * np.cos(lon - l0); sy = -rc * np.cos(phc) * np.sin(lon - l0); sz = rc * np.sin(phc)
ys = np.arctan(sz / sx); xs = np.arcsin(-sy / np.sqrt(sx**2 + sy**2 + sz**2))
ix = np.rint((xs - x[0]) / (x[1] - x[0])).astype(int); iy = np.rint((ys - y[0]) / (y[1] - y[0])).astype(int)
assert ix.min() >= 0 and iy.min() >= 0 and ix.max() < x.size and iy.max() < y.size, 'WRF grid outside sector %s' % PRD
# satellite zenith for record
vza = np.degrees(np.arccos(np.clip((H * np.cos(phc) * np.cos(lon - l0) - rc) / np.sqrt(sx**2 + sy**2 + sz**2), -1, 1)))
np.savez_compressed(out + '/grid.npz', ix=ix, iy=iy, vza=vza.astype('f4'))
n = 0
for f13 in files:
    s = re.search(r'_s(\d{11})', f13).group(1)  # YYYYJJJHHMM
    f08 = glob.glob(raw + '/OR_ABI-L2-CMIP%s-M*C08_G16_s%s*.nc' % (PRD, s))
    if not f08: print('NO_C08', s); continue
    bt = {}
    for c, f in (('c13', f13), ('c08', f08[0])):
        g = N.Dataset(f); v = g['CMI'][:]; bt[c] = np.ma.filled(v.astype('f4'), np.nan)[iy, ix]
        dqf = g['DQF'][:][iy, ix]; bt[c][dqf > 1] = np.nan; g.close()
    np.savez_compressed('%s/goes_s%s.npz' % (out, s), **bt); n += 1
    print(s, 'c13 min %.1f med %.1f nan %d' % (np.nanmin(bt['c13']), np.nanmedian(bt['c13']), np.isnan(bt['c13']).sum()))
print('REMAP_N', n)
