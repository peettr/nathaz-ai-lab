#!/usr/bin/env python3
"""Two-surrogate gate-0 qualification, development buildings only.

Data source: TPU Aerodynamic Database, Quan et al., ICWE12 2007.
No sealed H0=12 Cp member is opened: gate0.load_coordinates filters H0 first.
This program does NOT implement the downstream SHAP/IG gates.
"""
import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import gate0


def run(args):
    start = time.monotonic()
    coords = gate0.load_coordinates(args.coords)
    stats_hash = gate0.sha256(args.stats)
    expected = '7bff3edaef3b1a33c6623635caa2661e4e716203f1c4e99e62bf4ba6a37b3b92'
    if stats_hash != expected:
        raise RuntimeError('Unexpected stats hash; no Cp zip member opened')
    data = gate0.read_dev_stats(args.stats, coords)
    keys = sorted(data)
    roofs = sorted({d['roof'] for d in data.values()})
    groups = [k[0] for k in keys]
    folds = []
    for fold, (tri, tei) in enumerate(GroupKFold(n_splits=5).split(keys, groups=groups)):
        if args.pilot and fold:
            break
        train = [keys[i] for i in tri]
        test = [keys[i] for i in tei]
        x, y = gate0.features(train, data, roofs)
        xt, yt = gate0.features(test, data, roofs)
        models = {
            'gbm': HistGradientBoostingRegressor(max_iter=180, learning_rate=0.08,
                max_leaf_nodes=31, min_samples_leaf=30, l2_regularization=1.0,
                random_state=gate0.SEED),
            'mlp': make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(64, 64),
                activation='relu', solver='adam', batch_size=512, max_iter=120,
                early_stopping=True, n_iter_no_change=12, random_state=gate0.SEED)),
        }
        predictions = {}
        for name, model in models.items():
            t = time.monotonic()
            model.fit(x, y)
            predictions[name] = model.predict(xt)
            print(json.dumps({'fold': fold, 'model': name,
                'fit_predict_seconds': time.monotonic() - t}), flush=True)
        predictions['nearest'] = gate0.baseline(test, train, data, 'nearest')
        predictions['linear'] = gate0.baseline(test, train, data, 'linear')
        if any(len(v) != len(yt) for v in predictions.values()):
            raise RuntimeError('Prediction/target length mismatch')
        sse = {k: float(np.sum((v - yt)**2)) for k, v in predictions.items()}
        row = {'fold': fold, 'test_buildings': len({k[0] for k in test}),
               'n_points': len(yt), 'sse': sse,
               'rmse': {k: math.sqrt(v / len(yt)) for k, v in sse.items()}}
        folds.append(row)
        print(json.dumps(row), flush=True)
    n = sum(r['n_points'] for r in folds)
    pooled = {k: math.sqrt(sum(r['sse'][k] for r in folds) / n)
              for k in ('gbm', 'mlp', 'nearest', 'linear')}
    pass_models = {k: (not args.pilot and all(pooled[k] <= 0.9 * pooled[b]
                   for b in ('nearest', 'linear'))) for k in ('gbm', 'mlp')}
    result = {'source': gate0.SOURCE, 'status': 'pilot' if args.pilot else 'gate0_done',
              'folds': folds, 'pooled_rmse': pooled, 'pass_models': pass_models,
              'method': 'grouped 5-fold building CV; shared baselines, MLP train-fold-only scaling/early stopping',
              'mlp_spec': 'StandardScaler+MLPRegressor(64,64), adam, max_iter=120, early_stopping=True, seed=314159',
              'stats_sha256': stats_hash, 'coords_sha256': gate0.sha256(args.coords),
              'sealed_H0_12_members_opened': 0, 'elapsed_seconds': time.monotonic()-start}
    out = Path(args.out)
    if out.exists():
        raise FileExistsError(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'result': str(out), 'elapsed_seconds': result['elapsed_seconds']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--coords', required=True)
    parser.add_argument('--stats', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--pilot', action='store_true')
    run(parser.parse_args())
