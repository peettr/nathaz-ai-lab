#!/usr/bin/env python3
"""Read-only CRC status for exact registered roots."""
import collections,json,pathlib,subprocess
p=pathlib.Path('/groups/kareem/[用户]/L22_6/L22_6_v3S0_DBG_01_20261127/EXPERIMENT_CARD.md')
base=pathlib.Path('/groups/kareem/[用户]/L22_6')
roots=list(base.glob('L22_6_v3S0_*_20261127'))
state=collections.Counter()
rows=[]
for root in sorted(roots):
    label=root.name.removeprefix('L22_6_v3S0_').removesuffix('_20261127')
    if label.startswith('DBG'):continue
    ec=root/'run.exitcode'; m=root/'metrics.json'; log=root/'analyze.log'
    status=('exit_'+ec.read_text().strip() if ec.exists() else 'in_queue_or_running')
    if m.exists():status+=' metrics'
    if log.exists() and not m.exists():status+=' analyze_log'
    state[status]+=1
    rows.append({'group_seq':label,'status':status,'metrics_bytes':m.stat().st_size if m.exists() else None,'log_tail':log.read_text()[-250:] if log.exists() and not m.exists() else None})
print(json.dumps({'root_count':len(roots),'measurement_count':len(rows),'state':dict(state),'rows':[r for r in rows if r['status']!='in_queue_or_running']},ensure_ascii=False))
