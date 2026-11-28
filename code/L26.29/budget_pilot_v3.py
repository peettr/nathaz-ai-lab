#!/usr/bin/env python3
"""Read immutable v3 log evidence and generate conservative workload floor."""
import csv
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
text = (ROOT / 'pilot_v3_remote_evidence_20261120.txt').read_text()
ex = [float(x) for x in re.findall(r'ExecutionTime = ([\d.]+) s', text)]
co = [float(x) for x in re.findall(r'Courant Number mean: [\d.]+ max: ([\d.]+)', text)]
assert len(ex) == 60 and len(co) >= 60  # initial Courant line precedes Time=0.002
seconds_per_step = (ex[59] - ex[9]) / 50
assert max(co) <= 0.5
cores, dt, margin = 4, 0.002, 1.2
# The 21 nondimensional time units from disturbance at tau=0 to the
# right edge of R(alpha)'s tau=14..21 window are unavoidable. No spin-up,
# checkpoint creation, visualization, ramp or postprocessing is counted.
scenarios = [
    ('Step1_64_phase_minimum', 64, 21.0, 1.0),
    ('Step1_32_phase_minimum', 32, 21.0, 1.0),
    ('Step1_8_phase_minimum', 8, 21.0, 1.0),
    ('Step1_8x2_refinements_optimistic', 16, 21.0, 1.0),
    ('Step2_b_64_phase_ramp_only', 64, 89.0, 1.0),
    ('Step2_c_64_phase_ramp_only', 64, 100.0, 1.0),
    ('Step2_a_64_phase_ramp_only', 64, 222.0, 1.0),
]
rows = []
for label, n, duration, cost_multiplier in scenarios:
    steps_per_case = duration / dt
    core_hours = n * steps_per_case * seconds_per_step * cores * cost_multiplier / 3600
    rows.append(dict(scenario=label, phase_count=n, min_time_units=duration,
                     steps_per_case=round(steps_per_case), seconds_per_step=seconds_per_step,
                     cores=cores, core_hours_floor=round(core_hours, 4),
                     with_20pct_margin=round(core_hours * margin, 4),
                     note='lower bound; no baseline, checkpoint, spinup, refined-grid overhead'))
# For the extra two eight-phase refinement sets, unrealistically assign
# the SAME cost as the coarse run. Their true cost is greater.
refined_floor = rows[0]['core_hours_floor'] + 2 * rows[2]['core_hours_floor']
print('samples',len(ex),'s_per_step',seconds_per_step,'Co_max',max(co))
print('Step1 64 + 8 timestep + 8 mesh optimistic core-hour floor', refined_floor,
      'with margin',round(refined_floor*margin,4))
with (ROOT / 'pilot_v3_budget_floor_v2.csv').open('x', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
for row in rows:
    print(row['scenario'],row['core_hours_floor'],row['with_20pct_margin'])
