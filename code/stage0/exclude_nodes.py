#!/usr/bin/env python3
"""Change only not-yet-submitted staged run.sh node exclusions."""
import json
from pathlib import Path
p=Path('/groups/kareem/[用户]/L22_6/L22_6_v3S0_DBG_01_20261127/prepared_jobs.jsonl')
rows=[json.loads(s) for s in p.read_text().splitlines()]
assert len(rows)==42
for x in rows:
    if x['tag']=='CI_01': continue
    root=Path(x['root'])
    if (root/'run.exitcode').exists() or (root/'scheduler.log').exists(): raise RuntimeError(f'already started {root}')
    run=root/'run.sh'; text=run.read_text()
    old="#$ -l hostname='!d24cepyc154*'"
    new="#$ -l hostname='!d24cepyc154*&!d24cepyc161*&!d24cepyc162*&!d24cepyc160*'"
    if text.count(old)!=1: raise ValueError(run)
    run.write_text(text.replace(old,new))
print('updated',len(rows)-1,'unsubmitted scripts')
