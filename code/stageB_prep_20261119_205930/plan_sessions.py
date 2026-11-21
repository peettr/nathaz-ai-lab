#!/usr/bin/env python3
"""Stage-B A100 plan using A14 measured full-ledger throughput, not a run."""
import json, pathlib
r=pathlib.Path(__file__).resolve().parent
rate=5.4;budget=3.5;T=17950.3769
speed={'bounce':601.65,'t4':808.92,'t15':708.67}
# V0 5T + up to 3T additional, then 2T statistics. Per-case overhead
# covers extraction/SHA/ACK; fixed overhead includes build/upload/teardown.
per=30;fixed=300
planned={g:2*7*T/v for g,v in speed.items()}
worst={g:2*10*T/v for g,v in speed.items()}
plan={'rate_CU_per_hour':rate,'budget_CU':budget,'steps_per_T':round(T),
      'steps_per_second':speed,'per_case_overhead_s':per,'fixed_overhead_s':fixed,
      'planned_solver_s':sum(planned.values()),'worst_case_solver_s':sum(worst.values()),
      'planned_by_group_s':planned,'worst_by_group_s':worst,
      'planned_total_s':sum(planned.values())+6*per+fixed,
      'worst_total_s':sum(worst.values())+6*per+fixed,
      'available_s':budget*3600/rate,'remaining_at_worst_s':budget*3600/rate-(sum(worst.values())+6*per+fixed),
      'caution':'A14 speed includes ledger readback, not full B statistics producer; timing extrapolation is provisional'}
assert plan['remaining_at_worst_s']>0
(r/'SESSION_PLAN.json').write_text(json.dumps(plan,indent=2)+'\n')
print(json.dumps(plan,indent=2))
