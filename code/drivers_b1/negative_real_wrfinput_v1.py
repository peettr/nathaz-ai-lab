#!/usr/bin/env python3
"""Two independent negative copies of a real archived wrfinput; never modify source."""
import hashlib, json, shutil, sys
from pathlib import Path
import numpy as np
from netCDF4 import Dataset
from check_gc37x_inputs import check
root = Path(sys.argv[1]); original = root/'wrfinput_d01'
assert original.is_file() and not original.is_symlink()
out = root/'REAL_WRFINPUT_NEGATIVE_v1.json'
if out.exists(): raise FileExistsError(out)
source_hash = hashlib.file_digest(original.open('rb'), 'sha256').hexdigest()
baseline = check(original, 'wrfinput')
results = {}
for kind in ('constant_q', 'nan_q'):
    copy = root/f'wrfinput_d01.{kind}.nc'
    if copy.exists(): raise FileExistsError(copy)
    shutil.copyfile(original, copy)
    with Dataset(copy,'a') as ds:
        q = ds.variables['QVAPOR']
        assert 'bottom_top' in q.dimensions and q.shape[q.dimensions.index('bottom_top')] > 1
        if kind == 'constant_q': q[0,0,:,:] = 1e-6
        else: q[0,1,0,0] = np.nan
    res = check(copy,'wrfinput')
    token = 'constant_fake' if kind == 'constant_q' else 'nonfinite'
    caught = (not res['passed']) and any(token in e for e in res['errors'])
    results[kind] = {'copy':str(copy),'caught':caught,'matching_errors':[e for e in res['errors'] if token in e], 'all_errors':res['errors']}
report = {'source':str(original),'source_sha256':source_hash,'baseline':baseline,'negative_fixtures':results,'all_caught':all(v['caught'] for v in results.values())}
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'report':str(out),'all_caught':report['all_caught'],'baseline_passed':baseline['passed'],'errors':{k:v['matching_errors'] for k,v in results.items()}},ensure_ascii=False))
if not report['all_caught']: raise SystemExit(2)
