import hashlib
from pathlib import Path
p=Path('/content/m6')
for x in ('m6_score.py','config.json','models.json','train_summary.json'):
 f=p/x;print(x,hashlib.sha256(f.read_bytes()).hexdigest(),f.stat().st_size)
print('TRAIN_FILES',len(list((p/'train_gfs').glob('*.csv'))))
print('TEST_FILES',len(list((p/'test_gfs').glob('*.csv'))) if (p/'test_gfs').exists() else 0)
