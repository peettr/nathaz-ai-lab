#!/usr/bin/env python3
"""L22.11 映射核实：本次重跑 decomposePar 得到的 perm 与快试 1790176 候选 perm 逐元素比较（比解压后的数组，不比 gzip 字节：gzip 头含时间戳）。全同退出 0，否则 43。"""
import gzip, hashlib, io, json, sys
import numpy as np
new, old = sys.argv[1], sys.argv[2]
res, ok = {}, True
for g in ('medium', 'fine'):
    a = np.load(io.BytesIO(gzip.open(f'{new}/{g}/{g}_perm.npy.gz').read()))
    b = np.load(io.BytesIO(gzip.open(f'{old}/{g}/{g}_perm.npy.gz').read()))
    eq = a.shape == b.shape and bool(np.array_equal(a, b))
    res[g] = dict(n=int(a.size), equal=eq, n_diff=int((a != b).sum()) if a.shape == b.shape else None,
                  sha_new=hashlib.sha256(np.ascontiguousarray(a, dtype=np.int64).tobytes()).hexdigest(),
                  sha_old=hashlib.sha256(np.ascontiguousarray(b, dtype=np.int64).tobytes()).hexdigest())
    ok &= eq
json.dump(res, open(f'{new}/compare_perm.json', 'w'), indent=1); print(json.dumps(res, indent=1))
sys.exit(0 if ok else 43)
