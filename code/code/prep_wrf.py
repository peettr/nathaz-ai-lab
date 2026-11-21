"""L26.20: wrfout (d02) one time -> CRTM column binary for simbt.f90.
usage: python prep_wrf.py wrfout out.bin [--reff main|alt] [--stride N] [--maxcol M]
Cloud order: water, ice, rain, snow, graupel. Water content kg/m2 = q * dp / g.
Reff main (um): 20/40/400/600/800 (Niu & Zou 2024, PDF pp.11-12); alt: 10/30/300/600/600 (assumption, sensitivity only).
Satellite: GOES-16 at 75.2W (geostationary, 35786 km)."""
import sys, argparse, numpy as np
from netCDF4 import Dataset
ap = argparse.ArgumentParser(); ap.add_argument('wrf'); ap.add_argument('out')
ap.add_argument('--reff', default='main'); ap.add_argument('--stride', type=int, default=1)
ap.add_argument('--maxcol', type=int, default=0); ap.add_argument('--sublon', type=float, default=-75.2)
a = ap.parse_args()
G = 9.80665
REFF = {'main': [20., 40., 400., 600., 800.], 'alt': [10., 30., 300., 600., 600.]}[a.reff]
d = Dataset(a.wrf)
v = lambda n: d.variables[n][0].astype('f8')
p = v('P') + v('PB')                          # Pa, (k, j, i) bottom->top
th = v('T') + 300.0
t = th * (p / 1e5) ** 0.2857
qv = np.maximum(v('QVAPOR'), 1e-8)
hyd = [np.maximum(v(n), 0.0) for n in ('QCLOUD', 'QICE', 'QRAIN', 'QSNOW', 'QGRAUP')]
psfc = v('PSFC'); tsk = v('TSK'); xland = v('XLAND')
lat = v('XLAT'); lon = v('XLONG'); ptop = float(d.variables['P_TOP'][0])
nz, ny, nx = p.shape
# interfaces (bottom->top): psfc, midpoints, ptop
pint = np.empty((nz + 1, ny, nx)); pint[0] = psfc; pint[-1] = ptop
pint[1:-1] = 0.5 * (p[:-1] + p[1:])
dp = pint[:-1] - pint[1:]
# extension above model top (fixed tropical-like layers), top->bottom
ext_lev = np.array([0.5, 2., 5., 10., 20., 35., ptop / 100.])
ext_lev = ext_lev[ext_lev <= ptop / 100.]
ext_p = 0.5 * (ext_lev[:-1] + ext_lev[1:])
ext_t = np.interp(np.log(ext_p), np.log([0.5, 1., 10., 50., 100.]), [265., 270., 230., 210., 200.])
ne = len(ext_p); nl = ne + nz
def o3_ppmv(pp):  # rough tropical O3 climatology (assumption; IR window weakly sensitive)
    return np.interp(np.log(pp), np.log([0.5, 2., 10., 30., 100., 300., 1000.]), [3., 6., 9., 5., 0.3, 0.05, 0.03])
# satellite zenith angle
Re, H = 6371.0, 35786.0
la, dl = np.radians(lat), np.radians(lon - a.sublon)
cosg = np.cos(la) * np.cos(dl)
zen = np.degrees(np.arctan2(np.sqrt(1 - cosg ** 2) * (Re + H), (Re + H) * cosg - Re))
jj, ii = np.meshgrid(np.arange(0, ny, a.stride), np.arange(0, nx, a.stride), indexing='ij')
jj, ii = jj.ravel(), ii.ravel()
if a.maxcol: jj, ii = jj[:a.maxcol], ii[:a.maxcol]
np_ = len(jj)
with open(a.out, 'wb') as f:
    np.array([np_, nl, 5], dtype='<i4').tofile(f)
    for j, i in zip(jj, ii):
        pl = np.concatenate([ext_lev[:-1], pint[::-1, j, i] / 100.])
        pm = np.concatenate([ext_p, p[::-1, j, i] / 100.])
        tm = np.concatenate([ext_t, t[::-1, j, i]])
        qm = np.concatenate([np.full(ne, 0.003), qv[::-1, j, i] * 1000.])
        cw = np.zeros((nl, 5)); re = np.zeros((nl, 5))
        for c in range(5):
            cw[ne:, c] = hyd[c][::-1, j, i] * dp[::-1, j, i] / G
            re[ne:, c] = np.where(cw[ne:, c] > 0, REFF[c], 0.)
        rec = [pl, pm, tm, qm, o3_ppmv(pm), cw.T.ravel(), re.T.ravel(),
               [tsk[j, i]], [1.0 if xland[j, i] > 1.5 else 0.0], [min(zen[j, i], 80.)]]
        np.concatenate([np.asarray(x, 'f8') for x in rec]).astype('<f4').tofile(f)
np.savez_compressed(a.out + '.idx.npz', j=jj, i=ii, lat=lat[jj, ii], lon=lon[jj, ii], zen=zen[jj, ii])
print('PREP', np_, 'columns', nl, 'layers', 'ptop_hPa', ptop / 100.)
