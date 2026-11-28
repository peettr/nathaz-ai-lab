import hashlib
from pathlib import Path
for n in ('m6_score.py','config.json','m6_extract.py','stations.json'):
 p=Path('/content/m6')/n
 print(n,hashlib.sha256(p.read_bytes()).hexdigest())
