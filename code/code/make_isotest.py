"""L26.20 A1 analytic check: isothermal atmosphere + surface at T0 -> any channel BT must equal T0.
Profiles: 0 clear dry z=0; 1 clear moist z=50; 2 cloudy (all 5 types, thick) z=30; 3 tropical-like (descriptive only)."""
import numpy as np, sys
out = sys.argv[1]; T0 = 290.0; nl = 60
lev = np.geomspace(0.5, 1000., nl + 1); lay = 0.5 * (lev[:-1] + lev[1:]); dp = (lev[1:] - lev[:-1]) * 100.
o3 = np.interp(np.log(lay), np.log([0.5, 2., 10., 30., 100., 300., 1000.]), [3., 6., 9., 5., .3, .05, .03])
reff = [20., 40., 400., 600., 800.]
def rec(t, q, cw, tsk, zen):
    re = np.where(cw > 0, np.array(reff)[None, :], 0.)
    return np.concatenate([lev, lay, t, q, o3, cw.T.ravel(), re.T.ravel(), [tsk], [1.0], [zen]]).astype('<f4')
P = []
P.append(rec(np.full(nl, T0), np.full(nl, 1e-3), np.zeros((nl, 5)), T0, 0.))
P.append(rec(np.full(nl, T0), np.where(lay > 300, 15., 0.01), np.zeros((nl, 5)), T0, 50.))
cw = np.zeros((nl, 5)); m = (lay > 200) & (lay < 900); cw[m, :] = 0.05 * dp[m, None] / 9.80665 / 100.
P.append(rec(np.full(nl, T0), np.where(lay > 300, 15., 0.01), cw, T0, 30.))
ttrop = np.interp(lay, [0.5, 1., 10., 100., 200., 500., 850., 1000.], [265., 270., 230., 195., 220., 268., 290., 300.])
qtrop = np.interp(lay, [0.5, 300., 500., 850., 1000.], [0.003, 0.3, 3., 13., 18.])
P.append(rec(ttrop, qtrop, np.zeros((nl, 5)), 301., 30.))
with open(out, 'wb') as f:
    np.array([len(P), nl, 5], '<i4').tofile(f)
    for p in P: p.tofile(f)
print('ISOTEST written', len(P))
