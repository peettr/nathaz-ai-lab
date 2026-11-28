#!/usr/bin/env python3
"""Stage only frozen source inputs in a new v4 tarball."""
import tarfile,hashlib
from pathlib import Path
D=Path(__file__).resolve().parent;B=D.parent
files=['chain_a.py','events_verified.csv','v1/chain_a_v1.py','v1/run2/station_rows_v1.csv','s2/chain_b_s2a.py','s2/s2b/final/station_comparison.csv']
files += [f's2/s2b/track_{x.lower()}_pang_48.json' for x in ('BERYL','DEBBY','DELTA','FRANCINE','HELENE','IAN','MILTON','NICOLE','ZETA')]
files+=['v4_empirical/sample_list.csv']
p=D/'input_bundle.tar.gz'
if p.exists():raise FileExistsError(p)
with tarfile.open(p,'w:gz') as tar:
 for name in files:
  src=B/name;assert src.is_file(),src
  tar.add(src,arcname='b_tc/'+name)
print('bundle',len(files),p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())
