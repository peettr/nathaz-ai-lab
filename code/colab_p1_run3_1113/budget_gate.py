#!/usr/bin/env python3
"""Conservative wall-clock CU gate, conditional on observed rate."""
import argparse, json, math
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('pilot_json',type=Path)
p.add_argument('--already-cu',type=float,required=True)
p.add_argument('--rate-cu-per-hour',type=float,required=True)
p.add_argument('--budget-cu',type=float,default=1.5)
p.add_argument('--per-session-overhead-s',type=float,default=600)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
x=json.loads(a.pilot_json.read_text())
assert x['cpu_count']==2 and x['parallel']==2
rows=x['results']; assert len(rows)==2 and all(r['returncode']==0 for r in rows)
walls=[r['wall_s'] for r in rows]
parallel=max(walls)<=1.3*475
workers=2 if parallel else 1
single=max(walls) if parallel else 473.89
# Mean single-solve wall time under contention is the conservative max observed.
solves=132
pairs=math.ceil(solves/workers)
solve_s=pairs*single
# Keep each session below 3h with 120s stop margin and 600s staging/transfer.
useful_s=10800-120-a.per_session_overhead_s
sessions=math.ceil(solve_s/useful_s)
expected_s=solve_s+sessions*a.per_session_overhead_s
projected=a.already_cu+expected_s*a.rate_cu_per_hour/3600
out={'cpu_count':2,'observed_pair_wall_s':x['pair_wall_s'],'single_solve_wall_s':walls,'criterion_s':1.3*475,'workers':workers,'per_run_timeout_s':math.ceil(2*single),'solves':solves,'solve_wall_s':solve_s,'session_count':sessions,'overhead_each_s':a.per_session_overhead_s,'allocated_wall_s_estimate':expected_s,'previous_cu_conditional':a.already_cu,'rate_cu_per_hour':a.rate_cu_per_hour,'projected_total_cu':projected,'budget_cu':a.budget_cu,'allow':projected<=a.budget_cu}
assert not a.out.exists(),a.out
a.out.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(out,indent=2,ensure_ascii=False))
