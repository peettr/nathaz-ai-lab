#!/usr/bin/env python3
"""Synthetic control-flow smoke, never reads TPU Cp or production coordinates.
Run only within an allocated compute node. Forced gate advancement is NOT science.
"""
import argparse
import csv
import json
import tempfile
from pathlib import Path
import numpy as np
import gate0
import full_v3_r2 as worker


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix='l2616_synthetic_', dir=Path(a.out).parent) as tmp:
        root = Path(tmp)
        coords = root / 'synthetic_coordinates.csv'
        stats = root / 'synthetic_stats.npz'
        stats.write_bytes(b'SYNTHETIC PLACEHOLDER NO REAL CP')
        rows = []
        data = {}
        # 29 designs x four heights = 116 buildings; 29 at H0=12 are metadata only.
        for i in range(29):
            pitch = [5, 10, 14, 18, 22, 27, 30, 45][i % 8]
            depth = [16, 24, 40][i // 10]
            for h in (4, 8, 12, 16):
                case = f'SYN_{i:02d}_H{h:02d}'
                rows.append(dict(lib='noeaves', face_type='ROOF', case=case,
                                 roof='gable roof', pitch=pitch, H0=h, D=depth))
                if h == 12:
                    continue
                # Non-collinear synthetic tap triangle for the unchanged spatial baseline.
                points = np.array([[-.85, -.80], [-.80, -.70], [-.75, -.78]])
                for wind in range(0, 91, 15):
                    x = .015*pitch + .035*h + .011*depth + .002*wind
                    y = np.array([x + .10*u - .08*v for u, v in points])
                    data[(case, wind)] = dict(points=points, y=y,
                                              geom=np.array([pitch, h, depth], float), roof='gable roof')
        with coords.open('x', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        assert len(data) == 609 and len(rows) == 116
        old_hash = gate0.sha256
        old_stage0, old_summary, old_checkpoint = worker.stage0, worker.summary_metrics, worker.checkpoint
        gate0.load_coordinates = lambda path: {k: True for k, _ in data}
        gate0.read_dev_stats = lambda path, unused: data
        gate0.sha256 = lambda path: ('7bff3edaef3b1a33c6623635caa2661e4e716203f1c4e99e62bf4ba6a37b3b92'
                                     if str(path) == str(stats) else old_hash(path))
        def stage0_synthetic(*args):
            result = old_stage0(*args)
            print('SMOKE original gate0:', json.dumps(result['pass_models']), flush=True)
            result['smoke_forced_advance'] = True
            result['pass'] = True
            return result
        def summary_synthetic(*args):
            result = old_summary(*args)
            print('SMOKE summary raw min:', result['min_jaccard'], result['min_spearman'], flush=True)
            result['smoke_forced_advance'] = True
            result['pass'] = True
            return result
        def checkpoint_synthetic(out, result):
            if 'pass_components' in result['gate1']:
                print('SMOKE original gate1:', json.dumps(result['gate1']['pass_components']), flush=True)
                result['gate1']['smoke_forced_advance'] = True
                result['gate1']['pass'] = True
            old_checkpoint(out, result)
        worker.stage0 = stage0_synthetic
        worker.summary_metrics = summary_synthetic
        worker.checkpoint = checkpoint_synthetic
        worker.START = __import__('time').monotonic()
        worker.main(argparse.Namespace(out=a.out, coords=str(coords), stats=str(stats), soft_seconds=300))
        result = json.loads((Path(a.out) / 'gates_v3.json').read_text())
        print('SMOKE stage statuses:', {k: result[k].get('status', 'computed') for k in ('gate0','gate1','gate2','gate2b','predictions')}, flush=True)
        print('SMOKE gate1 components:', result['gate1'].get('pass_components'), flush=True)
        assert result['gate1']['pass'], 'Synthetic gate1 blocked full five-stage smoke'
        assert result['gate2']['status'] == result['gate2b']['status'] == 'done'
        assert (Path(a.out) / 'predictions_frozen.csv').is_file()
        print('SMOKE CSV written; forced advancement is not a scientific gate result', flush=True)

if __name__ == '__main__':
    main()
