"""L26.20 D1: simbt output + prep idx -> gridded BT npz (ny,nx) for ch08/ch13. usage: python grid_bt.py bt.bin idx.npz out.npz"""
import sys, numpy as np
n, nch = np.fromfile(sys.argv[1], '<i4', 2); bt = np.fromfile(sys.argv[1], '<f4', offset=8).reshape(n, nch)
ix = np.load(sys.argv[2]); j, i = ix['j'].ravel(), ix['i'].ravel()
ny, nx = j.max() + 1, i.max() + 1; o = {}
for k, c in enumerate(['c08', 'c13']):
    a = np.full((ny, nx), np.nan, 'f4'); a[j, i] = bt[:, k]; o[c] = a
np.savez_compressed(sys.argv[3], **o); print('GRID', sys.argv[3], 'c13 min %.1f med %.1f' % (np.nanmin(o['c13']), np.nanmedian(o['c13'])))
