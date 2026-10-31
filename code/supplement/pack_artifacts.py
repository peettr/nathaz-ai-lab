import tarfile,hashlib
from pathlib import Path
p=Path('/content/m6');out=p/'postreview'
files=['auc_site_ci.csv','topk_corrected.csv','groups.csv','site_mae.csv','B_D2_vs_P.csv','tau.csv','coverage_summary.csv']
for f in files:assert (out/f).exists(),f
t=p/'postreview_supplement_20261029.tgz'
with tarfile.open(t,'w:gz') as tar:
    for f in files:tar.add(out/f,arcname='postreview/'+f)
    tar.add(p/'rebuild_core/parity.json',arcname='postreview/parity.json')
    tar.add(p/'rebuild_core/rebuilt_main.csv',arcname='postreview/rebuilt_main.csv')
    for d in (3,4,6):tar.add(p/f'test_predictions_delay{d}.parquet',arcname=f'pairs/test_predictions_delay{d}.parquet')
    tar.add(p/'test_gfs_full_20261029.tgz',arcname='test_gfs/test_gfs_full_20261029.tgz')
print('TAR',t.stat().st_size,hashlib.sha256(t.read_bytes()).hexdigest())
for f in files:print(f,hashlib.sha256((out/f).read_bytes()).hexdigest())
for d in (3,4,6):print(f'test_predictions_delay{d}.parquet',hashlib.sha256((p/f'test_predictions_delay{d}.parquet').read_bytes()).hexdigest())
