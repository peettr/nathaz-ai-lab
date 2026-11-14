"""B0/B1/B2 on aligned raw-domain fluid pixels; no holdout fitting.

Caller must supply per-case arrays on the same raw grid as eval_module: target,
fluid mask (finite target >= 0), local height, signed distance, upwind obstacle
height/distance, and wind direction. Raw adapter is deliberately not guessed in
absence of the frozen CRC formatter and bundle; check parity before using.
"""
import numpy as np

FIELDS = ('height', 'sdf', 'upwind_height', 'upwind_distance')


def flatten(cases, require_target=True):
    parts = []
    for case in cases:
        mask = np.asarray(case['mask'], dtype=bool)
        shape = mask.shape
        features = []
        for key in FIELDS:
            a = np.asarray(case[key], dtype=np.float64)
            assert a.shape == shape, (key, a.shape, shape)
            features.append(a[mask])
        theta = np.deg2rad(float(case['direction_degrees']))
        features.extend((np.full(mask.sum(), np.sin(theta)), np.full(mask.sum(), np.cos(theta))))
        x = np.column_stack(features)
        assert np.isfinite(x).all()
        if require_target:
            y = np.asarray(case['target'], dtype=np.float64)
            assert y.shape == shape
            assert np.isfinite(y[mask]).all() and np.all(y[mask] >= 0)
            parts.append((x, y[mask]))
        else:
            parts.append(x)
    if require_target:
        return np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts])
    return parts


def score_cases(predict, cases):
    """Equal per-case R2 medians, raw valid-pixel pooled RMSE, case RMSE."""
    rows = []
    total_sq, total_n = 0.0, 0
    for case, x in zip(cases, flatten(cases, False)):
        y = np.asarray(case['target'])[np.asarray(case['mask'], bool)]
        yh = np.asarray(predict(x)).reshape(-1)
        assert yh.shape == y.shape and np.isfinite(yh).all()
        sq = float(np.sum((y - yh)**2))
        den = float(np.sum((y - y.mean())**2))
        r2 = 1 - sq / den if den > 0 else None
        rows.append({'case': case['name'], 'r2': r2, 'rmse': float(np.sqrt(sq/len(y))), 'n': len(y)})
        total_sq += sq
        total_n += len(y)
    return {'cases': rows, 'median_r2': float(np.median([r['r2'] for r in rows if r['r2'] is not None])),
            'pooled_rmse': float(np.sqrt(total_sq/total_n))}


class B0:
    def fit(self, train):
        _, y = flatten(train)
        self.mean = float(y.mean())
        return self

    def predict(self, x):
        return np.full(len(x), self.mean)


class B1:
    """Quantile lookup by SDF-derived distance and upwind height, train-only edges."""
    def __init__(self, bins=8):
        self.bins = bins  # implementation resolution: sensitivity/disclosure required

    def fit(self, train):
        x, y = flatten(train)
        self.mean = float(y.mean())
        self.edges = [np.unique(np.quantile(x[:, j], np.linspace(0, 1, self.bins+1)[1:-1]))
                      for j in (1, 2)]
        indexes = [np.searchsorted(e, x[:, j], side='right') for e, j in zip(self.edges, (1,2))]
        shape = tuple(len(e)+1 for e in self.edges)
        self.sums = np.zeros(shape)
        self.counts = np.zeros(shape, dtype=np.int64)
        np.add.at(self.sums, tuple(indexes), y)
        np.add.at(self.counts, tuple(indexes), 1)
        return self

    def predict(self, x):
        inds = tuple(np.searchsorted(e, x[:, j], side='right') for e,j in zip(self.edges,(1,2)))
        n = self.counts[inds]
        return np.divide(self.sums[inds], n, out=np.full(len(x), self.mean), where=n>0)


class B2:
    """Standardized ridge; alpha chosen on inner validation ONLY."""
    def __init__(self, alphas=(0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0)):
        self.alphas = alphas  # unreported prereg parameter; validate provenance/sensitivity

    def fit(self, train, val):
        x, y = flatten(train)
        self.center, self.scale = x.mean(axis=0), x.std(axis=0)
        self.scale[self.scale == 0] = 1
        # sufficient statistics avoid making a second full dense design matrix
        z = (x-self.center)/self.scale
        gram = z.T @ z
        rhs = z.T @ (y-y.mean())
        xv, yv = flatten(val)
        zv = (xv-self.center)/self.scale
        best = None
        for a in self.alphas:
            beta = np.linalg.solve(gram + float(a)*np.eye(x.shape[1]), rhs)
            pred = y.mean() + zv @ beta
            loss = float(np.mean((yv-pred)**2))
            if best is None or loss < best[0]:
                best = (loss, float(a), beta)
        self.alpha = best[1]
        self.beta = best[2]
        self.intercept = float(y.mean())
        return self

    def predict(self, x):
        return self.intercept + ((x-self.center)/self.scale) @ self.beta
