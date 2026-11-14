#!/usr/bin/env python3
"""L26.16 v3 gate 0; only dev-case zip members are opened.

TPU source: TPU Aerodynamic Database (Quan et al., ICWE12 2007), internal research.
R25.1-13: theta=0 wind from -x, theta=90 from -y; windward roof zone
uses projection s = u*cos(theta)+v*sin(theta): s< -1/3 windward,
|s|<=1/3 middle, s>1/3 leeward. Crosswind coordinate is
q = -u*sin(theta)+v*cos(theta), split at +/-1/3 left/centre/right.
These zones are descriptive and do not enter point-level gate-0 scoring.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

SOURCE = 'TPU Aerodynamic Database, Quan et al. (ICWE12 2007); internal research only'
ROOFS = {'flat roof': 0, 'gable roof': 1, 'hip roof': 2}
# Input table roof wording may differ; IDs are derived from the sorted labels below.
PITCH_SCALE, H_SCALE, D_SCALE = 45.0, 12.0, 24.0
SEED = 314159


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load_coordinates(path):
    groups = defaultdict(list)
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            if row['lib'] != 'noeaves' or row['face_type'] != 'ROOF':
                continue
            # H0 is inspected before opening any per-case Cp member.
            if float(row['H0']) == 12.0:
                continue
            groups[row['case']].append(row)
    if len(groups) != 87:
        raise RuntimeError(f'Expected exactly 87 dev buildings, got {len(groups)}')
    return groups


def read_dev_stats(stats, coordinates):
    data = {}
    with zipfile.ZipFile(stats) as z:
        names = set(z.namelist())
        for case, rows in sorted(coordinates.items()):
            taps = np.array([int(r['tap']) - 1 for r in rows])
            p = np.array([[float(r['u']), float(r['v'])] for r in rows])
            geom = np.array([float(rows[0][k]) for k in ('pitch', 'H0', 'D')])
            roof = rows[0]['roof']
            for angle in range(0, 91, 15):
                key = f'{case}_{angle:03d}.npy'
                if key not in names:
                    raise RuntimeError(f'Missing development member {key}')
                # A zip member for H0=12 is NEVER opened (even though it exists).
                arr = np.load(io.BytesIO(z.read(key)), allow_pickle=False)
                if arr.ndim != 2 or arr.shape[0] != 4 or taps.max() >= arr.shape[1]:
                    raise RuntimeError(f'Unexpected stats shape {key}: {arr.shape}')
                mean_cp = arr[0, taps].astype(float)
                if not np.all(np.isfinite(mean_cp)):
                    raise RuntimeError(f'Nonfinite mean Cp in {key}')
                data[(case, angle)] = dict(points=p, y=mean_cp, geom=geom, roof=roof)
    if len(data) != 609:
        raise RuntimeError(f'Expected 609 dev files; got {len(data)}')
    return data


def spatial_match(ref, target):
    src = ref['points']; dst = target['points']
    if len(src) < 3:
        return NearestNDInterpolator(src, ref['y'])(dst)
    linear = LinearNDInterpolator(src, ref['y'], fill_value=np.nan)(dst)
    missing = ~np.isfinite(linear)
    if np.any(missing):
        linear[missing] = NearestNDInterpolator(src, ref['y'])(dst[missing])
    return np.asarray(linear)


def design_distance(a, b):
    return np.linalg.norm((a-b)/np.array([PITCH_SCALE, H_SCALE, D_SCALE]))


def baseline(test, train, dataset, mode):
    out = []
    for key in test:
        obj = dataset[key]
        eligible = [(k, dataset[k]) for k in train
                    if k[1] == key[1] and dataset[k]['roof'] == obj['roof']]
        if not eligible:
            # No matched roof type in training: transparent fallback over same direction.
            eligible = [(k, dataset[k]) for k in train if k[1] == key[1]]
        ranked = sorted(eligible, key=lambda kv: (design_distance(obj['geom'], kv[1]['geom']), kv[0]))
        near_key, near_obj = ranked[0]
        near = spatial_match(near_obj, obj)
        if mode == 'nearest' or len(ranked) == 1:
            out.append(near); continue
        # Parameter-space piecewise linear interpolation: find train buildings on
        # opposite sides of a SINGLE varied design axis, identical in the other
        # two axes; rank candidate brackets by distance to target. If no bracket
        # exists (edge/extrapolation/unsupported roof), use nearest neighbour.
        candidates = []
        for axis in range(3):
            low = [(k, r) for k, r in eligible if r['geom'][axis] < obj['geom'][axis]
                   and np.allclose(np.delete(r['geom'], axis), np.delete(obj['geom'], axis))]
            high = [(k, r) for k, r in eligible if r['geom'][axis] > obj['geom'][axis]
                    and np.allclose(np.delete(r['geom'], axis), np.delete(obj['geom'], axis))]
            if low and high:
                a = max(low, key=lambda kr: kr[1]['geom'][axis]); b = min(high, key=lambda kr: kr[1]['geom'][axis])
                span = b[1]['geom'][axis] - a[1]['geom'][axis]
                candidates.append((span / [PITCH_SCALE, H_SCALE, D_SCALE][axis], a, b, axis))
        if candidates:
            _, a, b, axis = min(candidates, key=lambda c: c[0])
            x0, x1, xt = a[1]['geom'][axis], b[1]['geom'][axis], obj['geom'][axis]
            weight = (xt-x0)/(x1-x0)
            out.append((1-weight)*spatial_match(a[1], obj) + weight*spatial_match(b[1], obj))
        else:
            out.append(near)
    return np.concatenate(out)


def features(keys, dataset, roof_names):
    xx = []; yy = []
    for key in keys:
        ob = dataset[key]
        v = np.column_stack([np.full(len(ob['y']), roof_names.index(ob['roof'])),
                             np.tile(ob['geom'], (len(ob['y']), 1)),
                             np.full(len(ob['y']), key[1]), ob['points']])
        xx.append(v); yy.append(ob['y'])
    return np.vstack(xx), np.concatenate(yy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--coords', required=True)
    ap.add_argument('--stats', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--pilot', action='store_true')
    args = ap.parse_args()
    started = time.time()
    coordinates = load_coordinates(args.coords)
    stats_hash = sha256(args.stats)
    if stats_hash != '7bff3edaef3b1a33c6623635caa2661e4e716203f1c4e99e62bf4ba6a37b3b92':
        raise RuntimeError('Stats hash mismatch: halt before opening any member')
    dataset = read_dev_stats(args.stats, coordinates)
    roofs = sorted(set(o['roof'] for o in dataset.values()))
    keys = sorted(dataset)
    groups = np.array([k[0] for k in keys]); folds = GroupKFold(n_splits=5)
    scores = []
    for fold, (tr, te) in enumerate(folds.split(keys, groups=groups)):
        if args.pilot and fold > 0:
            break
        train = [keys[i] for i in tr]; test = [keys[i] for i in te]
        X, y = features(train, dataset, roofs)
        XT, yt = features(test, dataset, roofs)
        model = HistGradientBoostingRegressor(max_iter=180, learning_rate=0.08, max_leaf_nodes=31,
                                               min_samples_leaf=30, l2_regularization=1.0,
                                               random_state=SEED)
        model.fit(X, y)
        pred = model.predict(XT)
        b1 = baseline(test, train, dataset, 'nearest')
        b2 = baseline(test, train, dataset, 'linear')
        if not (len(yt) == len(pred) == len(b1) == len(b2)):
            raise RuntimeError('Prediction alignment mismatch')
        sq = {name: float(np.sum((val-yt)**2)) for name, val in
              [('surrogate', pred), ('nearest', b1), ('linear', b2)]}
        result = dict(fold=fold, train_cases=len(set(k[0] for k in train)),
                      test_cases=len(set(k[0] for k in test)), n_points=len(yt),
                      sse=sq, rmse={k:math.sqrt(v/len(yt)) for k, v in sq.items()})
        scores.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    n = sum(r['n_points'] for r in scores)
    pooled = {name: math.sqrt(sum(r['sse'][name] for r in scores)/n)
              for name in ('surrogate', 'nearest', 'linear')}
    passed = not args.pilot and all(pooled['surrogate'] <= 0.9*pooled[b]
                                    for b in ('nearest', 'linear'))
    result = dict(source=SOURCE, status='pilot' if args.pilot else 'gate0_done',
                  gate0=dict(threshold='surrogate RMSE <= 0.9 * each baseline RMSE',
                             folds=scores, pooled_rmse=pooled, pass_gate=passed),
                  methodology=dict(model='HistGradientBoostingRegressor', seed=SEED,
                                   grouping='entire building, GroupKFold 5',
                                   nearest='same roof and wind, design-space nearest, roof taps spatial linear interpolation; outside hull nearest',
                                   linear='same roof and wind, bracket along one geometric parameter with other two fixed; outside bracket use nearest; roof taps spatial linear interpolation'),
                  source_hashes={'stats_sha256':stats_hash, 'coords_sha256':sha256(args.coords)},
                  dev_cases=87, sealed_cases=29, stats_members_opened=len(dataset),
                  elapsed_seconds=time.time()-started)
    path = Path(args.out)
    if path.exists():
        raise FileExistsError(f'Refusing to overwrite existing result: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'result':str(path), 'elapsed_seconds':result['elapsed_seconds'],
                      'pass_gate':passed}), flush=True)

if __name__ == '__main__':
    main()
