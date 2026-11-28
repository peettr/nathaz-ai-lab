"""L26.20 D2: structure metrics (plan §1.2) and criteria B, C (plan §2) for one storm.
usage: python d2_metrics.py <storm> <wrf_run_dir_armA>,<wrf_run_dir_armB> <sim_dir_armA>,<sim_dir_armB> <obs_onwrf_dir> <recon_dir> <outdir> <armnames>
Operational definitions are fixed in 06_Logs/L26.20/EXPERIMENT_CARD_D2.md (written before running). No b-deck anywhere.
"""
import sys, os, glob, re, json, datetime as dt, numpy as np, netCDF4 as N
from scipy import ndimage as ndi

storm, wruns, sdirs, odir, rdir, out, arms = sys.argv[1:8]
wruns, sdirs, arms = wruns.split(','), sdirs.split(','), arms.split(',')
os.makedirs(out, exist_ok=True)
DX = 3.0  # km
RB, AB = 3.0, 10.0  # radial bin km, azimuth bin deg
NFSS = 11  # neighbourhood 11 px = 33 km (odd window nearest to 30 km)
RMAX = 400.0

w0 = sorted(glob.glob(wruns[0] + '/wrfout_d02_*'))
d = N.Dataset(w0[0]); LAT = d['XLAT'][0].astype('f8'); LON = d['XLONG'][0].astype('f8'); d.close()
NY, NX = LAT.shape
TIMES = [os.path.basename(f)[11:24] for f in w0][1:]  # drop initial time (D1 decision)

def ll2ij(la, lo):
    k = np.argmin((LAT - la)**2 + ((LON - lo) * np.cos(np.radians(la)))**2)
    return np.unravel_index(k, LAT.shape)

def sim_center(run, t):
    d = N.Dataset('%s/wrfout_d02_%s:00:00' % (run, t))
    ps = d['PSFC'][0].astype('f8'); h = d['HGT'][0].astype('f8'); t2 = d['T2'][0].astype('f8'); d.close()
    slp = ps * (1 - 0.0065 * h / (t2 + 0.0065 * h))**-5.257
    e = 10; s = np.full_like(slp, np.inf); s[e:-e, e:-e] = slp[e:-e, e:-e]
    j, i = np.unravel_index(np.argmin(s), s.shape)
    return float(j), float(i), float(slp[j, i] / 100)

def polar(cj, ci):
    jj, ii = np.mgrid[0:NY, 0:NX]
    dy, dx = (jj - cj) * DX, (ii - ci) * DX
    r = np.hypot(dx, dy); th = np.degrees(np.arctan2(dx, dy)) % 360
    return r, th

def metrics(T, cj, ci, thr=220., valid80=False):
    r, th = polar(cj, ci)
    m = r <= RMAX; rb = (r[m] // RB).astype(int); ab = (th[m] // AB).astype(int); tv = T[m]
    nab = int(360 / AB); nrb = int(RMAX // RB) + 1
    ok = np.isfinite(tv)
    aok = np.ones(nab, bool)
    if valid80:
        tot = np.bincount(ab, minlength=nab); good = np.bincount(ab[ok], minlength=nab)
        aok = good >= 0.8 * np.maximum(tot, 1)
    sel = ok & aok[ab]
    k = rb[sel] * nab + ab[sel]
    s = np.bincount(k, tv[sel], nrb * nab); c = np.bincount(k, None, nrb * nab)
    with np.errstate(invalid='ignore'):
        B = (s / np.where(c > 0, c, np.nan)).reshape(nrb, nab)
        Tbar = np.nanmean(B, axis=1)
    rc = (np.arange(nrb) + 0.5) * RB
    w = rc <= 150; kmin = int(np.nanargmin(np.where(w, Tbar, np.nan)))
    rew = float(rc[kmin])
    ring = sel & (np.abs(r[m] - rew) <= RB)
    eyem = sel & (r[m] < 0.5 * rew)
    Tring = float(np.nanmean(tv[ring])); Teye = float(np.nanmean(tv[eyem])) if eyem.any() else np.nan
    # ring closure: fraction of azimuth bins on ring with mean T < Teye - 5
    rs = np.bincount(ab[ring], tv[ring], nab); rcn = np.bincount(ab[ring], None, nab)
    with np.errstate(invalid='ignore'):
        ringaz = rs / np.where(rcn > 0, rcn, np.nan)
    closed = float(np.mean(ringaz[np.isfinite(ringaz)] < Teye - 5)) if np.isfinite(Teye) else 0.
    dT = Teye - Tring
    eye = bool(np.isfinite(dT) and dT >= 10 and closed >= 0.8)
    core = sel & (r[m] <= 100); band = sel & (r[m] > 100)
    fcore = float(np.mean(tv[core] < thr)); fband = float(np.mean(tv[band] < thr))
    def asym(msk):
        wv = np.maximum(thr - tv[msk], 0); a = ab[msk]
        ws = np.bincount(a, wv, nab); wc = np.bincount(a, None, nab)
        g = wc > 0
        if not g.any(): return np.nan, np.nan
        wa = ws[g] / wc[g]; thc = np.radians((np.arange(nab)[g] + 0.5) * AB)
        mean = wa.mean()
        if mean <= 0: return 0., np.nan
        z = 2 * np.mean(wa * np.exp(-1j * thc))
        return float(abs(z) / mean), float(np.degrees(np.angle(z)) % 360)  # direction (from north, clockwise) of max cold
    ra, rp = asym(ring); ba, bp = asym(band)
    return dict(r_ew=rew, eye=eye, dT_eye=float(dT), ring_closed=closed, f_core=fcore, f_band=fband,
                asym_ring_amp=ra, asym_ring_ph=rp, asym_band_amp=ba, asym_band_ph=bp)

def fit_circle(x, y):
    A = np.c_[x, y, np.ones_like(x)]; b = x**2 + y**2
    s = np.linalg.lstsq(A, b, rcond=None)[0]
    return s[1] / 2, s[0] / 2  # (y0, x0)

def obs_eye_center(T):
    """first guess: largest BT<220 K cluster -> warmest 9 km-smoothed pixel within 100 km of its centroid;
    then iterate: r_ew about centre, cold-ring pixels (0.5..1.5 r_ew, T < annulus mean) -> algebraic circle fit."""
    Tf = np.where(np.isfinite(T), T, 300.)
    lab, n = ndi.label(Tf < 220)
    if n == 0: return None
    big = 1 + int(np.argmax(ndi.sum(np.ones_like(Tf), lab, range(1, n + 1))))
    cj, ci = ndi.center_of_mass(lab == big)
    Ts = ndi.uniform_filter(Tf, 3)
    r, _ = polar(cj, ci); Tm = np.where(r <= 100, Ts, -np.inf)
    cj, ci = map(float, np.unravel_index(np.argmax(Tm), Tm.shape))
    for _ in range(5):
        mt = metrics(T, cj, ci); rew = mt['r_ew']
        r, _ = polar(cj, ci); ann = (r >= 0.5 * rew) & (r <= 1.5 * rew) & np.isfinite(T)
        if ann.sum() < 10: break
        cold = ann & (T < np.mean(T[ann]))
        jj, ii = np.nonzero(cold)
        y0, x0 = fit_circle(ii.astype('f8'), jj.astype('f8'))
        sh = np.hypot(y0 - cj, x0 - ci)
        if not np.isfinite(sh) or sh * DX > 50: break  # reject wild fits
        cj, ci = float(y0), float(x0)
        if sh < 1: break
    mt = metrics(T, cj, ci)
    return (cj, ci, mt) if mt['eye'] else None

def read_vdm():
    fx = []
    for f in sorted(glob.glob(rdir + '/*.txt')):
        s = open(f, errors='ignore').read()
        if 'VORTEX DATA MESSAGE' not in s: continue
        mA = re.search(r'\nA\.\s*(\d\d)/(\d\d):(\d\d):(\d\d)Z', s); mB = re.search(r'\nB\.\s*([\d.]+) deg ([NS])\s+([\d.]+) deg ([EW])', s)
        mh = re.search(r'URNT12 KNHC (\d{6})|URNT12 KWBC (\d{6})', s)
        if not (mA and mB): continue
        ym = re.search(r'\.(\d{6})\d{6}\.txt$', f).group(1)
        t = dt.datetime(int(ym[:4]), int(ym[4:6]), int(mA.group(1)), int(mA.group(2)), int(mA.group(3)), int(mA.group(4)))
        la = float(mB.group(1)) * (1 if mB.group(2) == 'N' else -1); lo = float(mB.group(3)) * (-1 if mB.group(4) == 'W' else 1)
        fx.append((t, la, lo, os.path.basename(f)))
    return fx

VDM = read_vdm()
def tparse(t): return dt.datetime.strptime(t, '%Y-%m-%d_%H')

def obs_file(t):
    tt = tparse(t); g = glob.glob('%s/goes_s%s*.npz' % (odir, tt.strftime('%Y%j%H')))
    return sorted(g)[0] if g else None

# ---------- observation side
OBS = {}
for t in TIMES:
    f = obs_file(t)
    if f is None: continue
    s = re.search(r'goes_s(\d{11})', f).group(1); scan = dt.datetime.strptime(s, '%Y%j%H%M')
    dtmin = abs((scan - tparse(t)).total_seconds()) / 60
    T = np.load(f)['c13']
    ec = obs_eye_center(T)
    if ec:
        cj, ci, mt = ec; src = 'IR_eye_fit'
    else:
        near = [v for v in VDM if abs((v[0] - tparse(t)).total_seconds()) <= 3600]
        if not near: OBS[t] = dict(src='none', dt_min=dtmin); continue
        v = min(near, key=lambda v: abs((v[0] - tparse(t)).total_seconds()))
        cj, ci = map(float, ll2ij(v[1], v[2])); src = 'VDM:' + v[3]; mt = metrics(T, cj, ci)
    near = [v for v in VDM if abs((v[0] - tparse(t)).total_seconds()) <= 3600]
    vsep = np.nan
    if near:
        v = min(near, key=lambda v: abs((v[0] - tparse(t)).total_seconds())); vj, vi = ll2ij(v[1], v[2])
        vsep = float(np.hypot(vj - cj, vi - ci) * DX)
    OBS[t] = dict(src=src, dt_min=dtmin, vdm_sep_km=vsep, cj=cj, ci=ci, lat=float(LAT[int(round(cj)), int(round(ci))]),
                  lon=float(LON[int(round(cj)), int(round(ci))]), T=T, **mt)

matched = [t for t in TIMES if t in OBS and OBS[t]['src'] != 'none' and OBS[t]['dt_min'] <= 5]

# ---------- criterion B (observation side only)
def cdiff(a, b): return abs((a - b + 180) % 360 - 180)
B = []
for t in matched:
    o = OBS[t]; T = o['T']; base = metrics(T, o['cj'], o['ci'])
    perts = [('c+y', dict(cj=o['cj'] + 1, ci=o['ci'])), ('c-y', dict(cj=o['cj'] - 1, ci=o['ci'])),
             ('c+x', dict(cj=o['cj'], ci=o['ci'] + 1)), ('c-x', dict(cj=o['cj'], ci=o['ci'] - 1)),
             ('thr215', dict(thr=215.)), ('thr225', dict(thr=225.)), ('valid80', dict(valid80=True))]
    row = dict(time=t)
    for name, kw in perts:
        a = dict(cj=o['cj'], ci=o['ci'], thr=220., valid80=False); a.update(kw)
        p = metrics(T, a['cj'], a['ci'], a['thr'], a['valid80'])
        row[name] = dict(r_ew_rel=abs(p['r_ew'] - base['r_ew']) / base['r_ew'], f_core=abs(p['f_core'] - base['f_core']),
                         f_band=abs(p['f_band'] - base['f_band']),
                         ph_ring=cdiff(p['asym_ring_ph'], base['asym_ring_ph']) if base['asym_ring_amp'] >= 0.1 else np.nan,
                         ph_band=cdiff(p['asym_band_ph'], base['asym_band_ph']) if base['asym_band_amp'] >= 0.1 else np.nan)
    for q in ['r_ew_rel', 'f_core', 'f_band', 'ph_ring', 'ph_band']:
        vals = [row[n][q] for n, _ in perts]
        row['max_' + q] = float(np.nanmax(vals)) if np.isfinite(vals).any() else np.nan
    B.append(row)
def nmed(x):
    x = np.array(x, float); return float(np.nanmedian(x)) if np.isfinite(x).any() else np.nan
Bsum = {q: nmed([r['max_' + q] for r in B]) for q in ['r_ew_rel', 'f_core', 'f_band', 'ph_ring', 'ph_band']}
Bsum['n'] = len(B)
Bsum['pass'] = bool(len(B) > 0 and Bsum['r_ew_rel'] <= 0.15 and Bsum['f_core'] <= 0.10 and Bsum['f_band'] <= 0.10
                    and all(not np.isfinite(Bsum[q]) or Bsum[q] <= 45 for q in ['ph_ring', 'ph_band']))
Bsum['per_type_median'] = {n: {q: nmed([r[n][q] for r in B]) for q in ['r_ew_rel', 'f_core', 'f_band', 'ph_ring', 'ph_band']}
                           for n in ['c+y', 'c-y', 'c+x', 'c-x', 'thr215', 'thr225', 'valid80']}

# ---------- FSS (each field centred on its own centre)
H = int(RMAX // DX)
def box(T, cj, ci):
    cj, ci = int(round(cj)), int(round(ci)); o = np.full((2 * H + 1, 2 * H + 1), np.nan, 'f4')
    j0, j1, i0, i1 = cj - H, cj + H + 1, ci - H, ci + H + 1
    a0, b0 = max(j0, 0), max(i0, 0); a1, b1 = min(j1, NY), min(i1, NX)
    o[a0 - j0:a1 - j0, b0 - i0:b1 - i0] = T[a0:a1, b0:b1]; return o
yy, xx = np.mgrid[-H:H + 1, -H:H + 1]; CIRC = np.hypot(yy, xx) * DX <= RMAX
def fss(Tm, To, thr=220.):
    v = np.isfinite(Tm) & np.isfinite(To)
    Pm = ndi.uniform_filter(((Tm < thr) & v).astype('f8'), NFSS, mode='constant')
    Po = ndi.uniform_filter(((To < thr) & v).astype('f8'), NFSS, mode='constant')
    k = CIRC & v; den = np.sum(Pm[k]**2) + np.sum(Po[k]**2)
    return float(1 - np.sum((Pm[k] - Po[k])**2) / den) if den > 0 else np.nan

rows = []; Csum = {}
for arm, run, sd in zip(arms, wruns, sdirs):
    for reff in ['main', 'alt']:
        dif = []
        for t in TIMES:
            sf = '%s_%s/bt_%s.npz' % (sd, reff, t)
            if not os.path.exists(sf): continue
            Ts = np.load(sf)['c13']; sj, si, pmin = sim_center(run, t)
            ms = metrics(Ts, sj, si)
            r = dict(storm=storm, arm=arm, reff=reff, time=t, sim_cj=sj, sim_ci=si, sim_lat=float(LAT[int(sj), int(si)]),
                     sim_lon=float(LON[int(sj), int(si)]), sim_pmin_hPa=pmin, **{'sim_' + k: v for k, v in ms.items()})
            if t in OBS and OBS[t]['src'] != 'none':
                o = OBS[t]
                r.update(obs_src=o['src'], obs_dt_min=o['dt_min'], obs_vdm_sep_km=o['vdm_sep_km'], obs_lat=o['lat'], obs_lon=o['lon'],
                         **{'obs_' + k: o[k] for k in ['r_ew', 'eye', 'dT_eye', 'ring_closed', 'f_core', 'f_band',
                                                       'asym_ring_amp', 'asym_ring_ph', 'asym_band_amp', 'asym_band_ph']})
                r['center_sep_km'] = float(np.hypot(sj - o['cj'], si - o['ci']) * DX)
                bm = box(Ts, sj, si); r['fss_same'] = fss(bm, box(o['T'], o['cj'], o['ci']))
                lag = []
                for h in (-12, 12):
                    t2 = (tparse(t) + dt.timedelta(hours=h)).strftime('%Y-%m-%d_%H')
                    if t2 in OBS and OBS[t2]['src'] != 'none':
                        f2 = fss(bm, box(OBS[t2]['T'], OBS[t2]['cj'], OBS[t2]['ci'])); r['fss_%+d' % h] = f2; lag.append(f2)
                if lag and np.isfinite(r['fss_same']) and np.isfinite(lag).any():
                    r['fss_lagmax'] = float(np.nanmax(lag)); r['fss_diff'] = r['fss_same'] - r['fss_lagmax']
                    if t in matched: dif.append(r['fss_diff'])
            rows.append(r)
        dif = np.array(dif)
        Csum['%s_%s' % (arm, reff)] = dict(n=int(dif.size), frac_better=float(np.mean(dif > 0)) if dif.size else np.nan,
                                          median_diff=float(np.median(dif)) if dif.size else np.nan,
                                          pass_=bool(dif.size > 0 and np.mean(dif > 0) >= 2 / 3 and np.median(dif) >= 0.05))
Csum['pass_main_both_arms'] = all(Csum['%s_main' % a]['pass_'] for a in arms)

summ = dict(storm=storm, times=len(TIMES), obs_center_sources={s: sum(1 for t in OBS if OBS[t]['src'].split(':')[0] == s) for s in ['IR_eye_fit', 'VDM', 'none']},
            matched_times=len(matched), matched=matched, B=Bsum, C=Csum, fss_window_px=NFSS)
json.dump(summ, open(out + '/summary_%s.json' % storm, 'w'), indent=1, default=float)
json.dump(B, open(out + '/B_perturb_%s.json' % storm, 'w'), indent=1, default=float)
import csv
keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in ('storm', 'arm', 'reff', 'time'), k))
with open(out + '/table_%s.csv' % storm, 'w', newline='') as f:
    wr = csv.DictWriter(f, keys); wr.writeheader(); wr.writerows(rows)
print(json.dumps(summ, indent=1, default=float))
