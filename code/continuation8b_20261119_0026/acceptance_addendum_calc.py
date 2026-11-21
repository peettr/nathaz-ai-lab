#!/usr/bin/env python3
"""Read-only sources: quantify prior E3 wall stress and byte-compare emitted kernels."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
from statistics import mean

root = Path(__file__).resolve().parent
prior = root.parent / 'continuation7_20261118_231514' / 'session_luw-t15-a100-19309021' / 'evidence' / 'E3_native_native_e3.csv.gz'
record_sha = hashlib.sha256(prior.read_bytes()).hexdigest()
assert record_sha == 'b09e385804fc5ad3d937773708fe38ac404b58a6b8c2de28ccbf7c253574cb26'
selected = {0, 1, 2, 100, 1200, 12000}
by_step = {n: [] for n in selected}
with gzip.open(prior, 'rt', newline='') as source:
    for row in csv.DictReader(source):
        step = int(row['step'])
        if step in by_step:
            by_step[step].append(row)
assert all(len(rows) == 64 for rows in by_step.values())
force = []
for step in sorted(selected):
    rows = by_step[step]
    tau = mean(float(row['tau_f_abs_lattice']) for row in rows)
    fx = mean(float(row['applied_force_x_lattice']) for row in rows)
    # 64 interior sample columns, not an exhaustive 400-column wall-field mean.
    force.append({'step': step, 'sample_columns': len(rows), 'sample_mean_tau_f': tau,
                  'sample_mean_applied_fx': fx,
                  'interior_area_weighted_tau_proxy': tau * 400 / 576,
                  'interior_area_weighted_fx_proxy': fx * 400 / 576})
kernels = {}
for variant in ('off', 'on', 'k3'):
    old = root / f'{variant}_old_kernel_container.cl'
    new = root / f'{variant}_new_kernel_container.cl'
    old_bytes, new_bytes = old.read_bytes(), new.read_bytes()
    old_sha = hashlib.sha256(old_bytes).hexdigest()
    new_sha = hashlib.sha256(new_bytes).hexdigest()
    assert old_bytes == new_bytes and old_sha == new_sha
    kernels[variant] = {'old_path': str(old), 'new_path': str(new),
                        'old_sha256': old_sha, 'new_sha256': new_sha,
                        'byte_equal': True, 'diff_bytes': 0}
result = {'prior_step_records': str(prior), 'prior_records_sha256': record_sha,
          'force_samples': force, 'forcing_stress_FH': 1e-5,
          'excluded_bounce_drag_proxy': 0.00029793764739862,
          'top_distribution_momentum_flux': None,
          'limits': 'tau_f/fx are measured at 64 interior columns in continuation7; scaling by 400/576 is an order proxy, not a measured full-wall force. The bounce resistance and top distribution flux were not measured.',
          'production_macro_off_byte_comparison': kernels}
output = root / 'ACCEPTANCE_ADDENDUM_3.json'
assert not output.exists(), output
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
