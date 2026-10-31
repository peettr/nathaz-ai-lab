"""L26.3 J1: download each TPU high-rise .mat, compute face-averaged Cp stats, delete the raw file.
Usage: python -I tpu_stats.py file_list.txt out.csv workdir
Raw TPU data are not kept (internal use only, no redistribution)."""
import csv, hashlib, os, subprocess, sys, time
import numpy as np
from scipy.io import loadmat

def cell_widths(c, lo, hi):
    c = np.sort(np.unique(c)); mid = (c[1:] + c[:-1]) / 2
    edges = np.concatenate([[lo], mid, [hi]]); return dict(zip(c, np.diff(edges)))

def face_weights(loc, B, D, H):
    x, z, f = loc[0], loc[1], loc[3].astype(int)
    bounds = {1: (0, B), 2: (B, B + D), 3: (B + D, 2 * B + D), 4: (2 * B + D, 2 * B + 2 * D)}
    w = np.zeros(x.size)
    for k, (lo, hi) in bounds.items():
        m = f == k
        wx = cell_widths(x[m], lo, hi); wz = cell_widths(z[m], 0, H)
        w[m] = [wx[a] * wz[b] for a, b in zip(x[m], z[m])]
    return f, w

def main(listf, outf, work):
    os.makedirs(work, exist_ok=True)
    done = set()
    if os.path.exists(outf):
        with open(outf) as fh: done = {(r['case'], int(r['theta'])) for r in csv.DictReader(fh)}
    fields = ['case', 'theta', 'B', 'D', 'H', 'alpha', 'Uh', 'fs', 'n_samples', 'n_taps', 'sha256', 'uniform_grid'] + \
             [f'{s}_f{k}_{w}' for k in (1, 2, 3, 4) for s in ('mean', 'std') for w in ('aw', 'eq')]
    new = not os.path.exists(outf)
    with open(outf, 'a', newline='') as fo:
        wr = csv.DictWriter(fo, fieldnames=fields)
        if new: wr.writeheader()
        for line in open(listf):
            case, th, url = line.split(); th = int(th)
            if (case, th) in done: continue
            p = os.path.join(work, f'{case}_{th}.mat')
            for attempt in range(3):
                r = subprocess.run(['curl', '-sS', '-f', '-m', '600', '-o', p, url])
                if r.returncode == 0: break
                time.sleep(10)
            else:
                print('FAIL', case, th, flush=True); continue
            sha = hashlib.sha256(open(p, 'rb').read()).hexdigest()
            d = loadmat(p)
            cp = d['Wind_pressure_coefficients'].astype(np.float64); loc = d['Location_of_measured_points']
            B = float(d['Building_breadth'][0, 0]); D = float(d['Building_depth'][0, 0]); H = float(d['Building_height'][0, 0])
            assert int(d['Wind_direction_angle'][0, 0]) == th
            f, w = face_weights(loc, B, D, H)
            row = dict(case=case, theta=th, B=B, D=D, H=H, alpha=0.25 if case.endswith('_4') else 1 / 6,
                       Uh=float(str(d['Uh_AverageWindSpeed'][0]).strip()), fs=int(d['Sample_frequency'][0, 0]),
                       n_samples=cp.shape[0], n_taps=cp.shape[1], sha256=sha)
            uni = True
            for k in (1, 2, 3, 4):
                m = f == k; wk = w[m] / w[m].sum()
                uni &= bool(np.allclose(wk, 1 / m.sum(), rtol=1e-3))
                for tag, ww in (('aw', wk), ('eq', np.full(m.sum(), 1 / m.sum()))):
                    ts = cp[:, m] @ ww
                    row[f'mean_f{k}_{tag}'] = ts.mean(); row[f'std_f{k}_{tag}'] = ts.std(ddof=1)
            row['uniform_grid'] = uni
            wr.writerow(row); fo.flush(); os.remove(p)
            print('OK', case, th, round(row['mean_f1_aw'], 3), round(row['std_f1_aw'], 3), flush=True)

if __name__ == '__main__':
    main(*sys.argv[1:4])
