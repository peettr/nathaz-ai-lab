#!/usr/bin/env python3
"""T18 path-contract draft; local --dry-run executes this actual worker with stub solver."""
import argparse,hashlib,json,math,tarfile,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--dry-run',action='store_true');a=p.parse_args()
m=json.loads(a.manifest.read_text())
assert set(m['candidates'])=={'K1a','K1b','K2','K3a','K3b'}
for name,archive in m['candidates'].items():
    source=Path(archive)
    if a.dry_run and source.parent==Path('/content'):
        source=Path(os.environ['T18_LOCAL_CONTENT'])/source.name
    if not source.is_file():raise FileNotFoundError(source)
    print('OPEN',source)
    with tarfile.open(source) as tf:
        members=tf.getnames();assert 'src/kernel.cpp' in members and 'src/setup.cpp' in members
    if not a.dry_run:raise RuntimeError('Draft is dry-run only; no GPU run is authorized')
    print('STUB_SOLVER',name,'3T=53851, 25T+2T window; no physical data produced')
print('WORKER_DRYRUN_OK candidates=5')
